# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

import bpy, datetime, mathutils, os, bmesh, shutil, sys, gc, math
from os import rename
import numpy
from numpy import arange, histogram, array, int8
import bpy_extras.io_utils as io_utils
from subprocess import Popen, PIPE, call
from collections import OrderedDict
from datetime import datetime as dt
from math import cos, sin, pi, ceil, tan
from time import sleep
from multiprocessing import Pool

try:
    import matplotlib.pyplot as plt
    import matplotlib.cm as cm
    mp = 1
    
except Exception as e:
    print('Matplotlib problem:', e)    
    mp = 0

from .livi_export import radgexport, spfc, createoconv, createradfile, genbsdf
from .livi_calc  import li_calc
from .vi_display import li_display, linumdisplay, spnumdisplay, en_air, en_panel, en_temp_panel, wr_legend, wr_disp, wr_scatter, wr_table, ss_disp, ss_legend, basic_legend, basic_table, basic_disp, ss_scatter, en_disp, en_pdisp, en_scatter, en_table, en_barchart, comp_table, comp_disp, leed_scatter, cbdm_disp, cbdm_scatter, envals, bsdf, bsdf_disp#, en_barchart, li3D_legend
from .envi_export import enpolymatexport, pregeo
from .envi_mat import envi_materials, envi_constructions
from .vi_func import selobj, livisimacc, solarPosition, wr_axes, clearscene, clearfiles, viparams, objmode, nodecolour, cmap, wind_rose, compass, windnum
from .vi_func import fvcdwrite, fvbmwrite, fvblbmgen, fvvarwrite, fvsolwrite, fvschwrite, fvtppwrite, fvraswrite, fvshmwrite, fvmqwrite, fvsfewrite, fvobjwrite, sunposenvi, clearlayers
from .vi_func import retobjs, rettree, retpmap, progressbar, spathrange, objoin, progressfile, chunks, xy2radial, logentry
from .envi_func import processf, retenvires, envizres, envilres, recalculate_text
from .vi_chart import chart_disp
#from .vi_gen import vigen

envi_mats = envi_materials()
envi_cons = envi_constructions()

class NODE_OT_LiGExport(bpy.types.Operator):
    bl_idname = "node.ligexport"
    bl_label = "LiVi geometry export"
    nodeid = bpy.props.StringProperty()

    def invoke(self, context, event):
        scene = context.scene
        if viparams(self, scene):
            return {'CANCELLED'}
        scene['viparams']['vidisp'] = ''
        scene['viparams']['viexpcontext'] = 'LiVi Geometry'
        objmode()
        clearfiles(scene['liparams']['objfilebase'])
        clearfiles(scene['liparams']['lightfilebase'])
        node = bpy.data.node_groups[self.nodeid.split('@')[1]].nodes[self.nodeid.split('@')[0]]
        node.preexport(scene)
        radgexport(self, node)
        node.postexport(scene)
        return {'FINISHED'}
        
class OBJECT_GenBSDF(bpy.types.Operator):
    bl_idname = "object.gen_bsdf"
    bl_label = "Gen BSDF"
    bl_description = "Generate a BSDF for the current selected object"
    bl_register = True
    bl_undo = False
    
    def execute(self, context):
        o = context.active_object
        genbsdf(context.scene, self, o)
        return {'FINISHED'}
        
class MATERIAL_LoadBSDF(bpy.types.Operator, io_utils.ImportHelper):
    bl_idname = "material.load_bsdf"
    bl_label = "Select BSDF file"
    filename_ext = ".XML;.xml;"
    filter_glob = bpy.props.StringProperty(default="*.XML;*.xml;", options={'HIDDEN'})
    filepath = bpy.props.StringProperty(subtype='FILE_PATH', options={'HIDDEN', 'SKIP_SAVE'})
    
    def draw(self,context):
        layout = self.layout
        row = layout.row()
        row.label(text="Import BSDF XML file with the file browser", icon='WORLD_DATA')
        row = layout.row()

    def execute(self, context):
        context.material['bsdf'] = {}
        if " " in self.filepath:
            self.report({'ERROR'}, "There is a space either in the filename or its directory location. Remove this space and retry opening the file.")
            return {'CANCELLED'}
        else:
            with open(self.filepath, 'r') as bsdffile:
                context.material['bsdf']['xml'] = bsdffile.read()
            return {'FINISHED'}

    def invoke(self,context,event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
    
class MATERIAL_DelBSDF(bpy.types.Operator):
    bl_idname = "material.del_bsdf"
    bl_label = "Del BSDF"
    bl_description = "Delete a BSDF for the current selected object"
    bl_register = True
    bl_undo = False
    
    def execute(self, context):
#        o = context.active_object
        del context.material['bsdf']
        return {'FINISHED'}
        
class MATERIAL_SaveBSDF(bpy.types.Operator):
    bl_idname = "material.save_bsdf"
    bl_label = "ave BSDF"
    bl_description = "Save a BSDF for the current selected object"
    bl_register = True
#    bl_undo = True
    filename_ext = ".XML;.xml;"
    filter_glob = bpy.props.StringProperty(default="*.XML;*.xml;", options={'HIDDEN'})
    filepath = bpy.props.StringProperty(subtype='FILE_PATH', options={'HIDDEN', 'SKIP_SAVE'})
    
    def draw(self,context):
        layout = self.layout
        row = layout.row()
        row.label(text="Save BSDF XML file with the file browser", icon='WORLD_DATA')

    def execute(self, context):
        with open(self.filepath, 'w') as bsdfsave:
            bsdfsave.write(context.material['bsdf']['xml'])
        return {'FINISHED'}

    def invoke(self,context,event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
        
class VIEW3D_OT_BSDF_Disp(bpy.types.Operator):
    bl_idname = "view3d.bsdf_display"
    bl_label = "BSDF display"
    bl_description = "Display BSDF"
    bl_register = True
    bl_undo = False
        
    def modal(self, context, event):
        if event.type != 'INBETWEEN_MOUSEMOVE' and context.region and context.area.type == 'VIEW_3D' and context.region.type == 'WINDOW':  
            if context.scene['viparams']['vidisp'] != 'bsdf_panel':
                self.remove(context)
                return {'CANCELLED'}
#        if context.region and context.area.type == 'VIEW_3D' and context.region.type == 'WINDOW': 
            mx, my = event.mouse_region_x, event.mouse_region_y
            if self.bsdf.spos[0] < mx < self.bsdf.epos[0] and self.bsdf.spos[1] < my < self.bsdf.epos[1]:
                self.bsdf.hl = (0, 1, 1, 1)  
                
                if event.type == 'LEFTMOUSE':
                    if event.value == 'PRESS':
                        self.bsdfpress = 1
                        self.bsdfmove = 0
                        return {'RUNNING_MODAL'}
                    elif event.value == 'RELEASE':
                        if not self.bsdfmove:
                            self.bsdf.expand = 0 if self.bsdf.expand else 1
                        self.bsdfpress = 0
                        self.bsdfmove = 0
                        context.area.tag_redraw()
                        return {'RUNNING_MODAL'}
                        
                elif event.type == 'ESC':
                    self.remove(context)
                    return {'CANCELLED'}                   
                elif self.bsdfpress and event.type == 'MOUSEMOVE':
                     self.bsdfmove = 1
                     self.bsdfpress = 0
                            
            elif abs(self.bsdf.lepos[0] - mx) < 10 and abs(self.bsdf.lspos[1] - my) < 10:
                self.bsdf.hl = (0, 1, 1, 1) 
                if event.type == 'LEFTMOUSE':
                    if event.value == 'PRESS':
                        self.bsdf.resize = 1
                    if self.bsdf.resize and event.value == 'RELEASE':
                        self.bsdf.resize = 0
                    return {'RUNNING_MODAL'}  
            
            elif all((self.bsdf.expand, self.bsdf.lspos[0] + 0.45 * self.bsdf.xdiff < mx < self.bsdf.lspos[0] + 0.8 * self.bsdf.xdiff, self.bsdf.lspos[1] + 0.06 * self.bsdf.ydiff < my < self.bsdf.lepos[1] - 5)):
                if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
                    self.bsdf.plt.show()
            
            else:
                for butrange in self.bsdf.buttons:
                    if self.bsdf.buttons[butrange][0] - 0.0075 * self.bsdf.xdiff < mx < self.bsdf.buttons[butrange][0] + 0.0075 * self.bsdf.xdiff and self.bsdf.buttons[butrange][1] - 0.01 * self.bsdf.ydiff < my < self.bsdf.buttons[butrange][1] + 0.01 * self.bsdf.ydiff:
                        if event.type == 'LEFTMOUSE' and event.value == 'PRESS' and self.bsdf.expand:
                            if butrange in ('Front', 'Back'):
                                self.bsdf.dir_select = butrange
                            elif butrange in ('Visible', 'Solar', 'Discrete'):
                                self.bsdf.rad_select = butrange
                            elif butrange in ('Transmission', 'Reflection'):
                                self.bsdf.type_select = butrange
                            self.bsdf.plot(context)
                            self.bsdf.save(context.scene)

                self.bsdf.hl = (1, 1, 1, 1)
                                
            if event.type == 'MOUSEMOVE':                
                if self.bsdfmove:
                    self.bsdf.pos = [mx, my]
                    context.area.tag_redraw()
                    return {'RUNNING_MODAL'}
                if self.bsdf.resize:
                    self.bsdf.lepos[0], self.bsdf.lspos[1] = mx, my
            
            if self.bsdf.expand and self.bsdf.lspos[0] < mx < self.bsdf.lepos[0] and self.bsdf.lspos[1] < my < self.bsdf.lepos[1]:
                theta, phi = xy2radial(self.bsdf.centre, (mx, my), self.bsdf.pw, self.bsdf.ph)
                phi = math.atan2(-my + self.bsdf.centre[1], mx - self.bsdf.centre[0]) + math.pi

                if theta < self.bsdf.radii[-1]:
                    for ri, r in enumerate(self.bsdf.radii):
                        if theta < r:
                            break

                    upperangles = [p * 2 * math.pi/self.bsdf.phis[ri] + math.pi/self.bsdf.phis[ri]  for p in range(int(self.bsdf.phis[ri]))]
                    uai = 0

                    if ri > 0:
                        for uai, ua in enumerate(upperangles): 
                            if phi > upperangles[-1]:
                                uai = 0
                                break
                            if phi < ua:
                                break

                    self.bsdf.patch_hl = sum(self.bsdf.phis[0:ri]) + uai
                    if event.type in ('LEFTMOUSE', 'RIGHTMOUSE')  and event.value == 'PRESS':                        
                        self.bsdf.num_disp = 1 if event.type == 'RIGHTMOUSE' else 0    
                        self.bsdf.patch_select = sum(self.bsdf.phis[0:ri]) + uai
                        self.bsdf.plot(context)
                        self.bsdf.save(context.scene)
                        context.area.tag_redraw()
                        return {'RUNNING_MODAL'}
                        
                else:
                    self.bsdf.patch_hl = None
                    
            if self.bsdf.expand and any((self.bsdf.leg_max != context.scene.vi_bsdfleg_max, self.bsdf.leg_min != context.scene.vi_bsdfleg_min, self.bsdf.col != context.scene.vi_leg_col, self.bsdf.scale_select != context.scene.vi_leg_scale)):
                self.bsdf.col = context.scene.vi_leg_col
                self.bsdf.leg_max = context.scene.vi_bsdfleg_max
                self.bsdf.leg_min = context.scene.vi_bsdfleg_min
                self.bsdf.scale_select = context.scene.vi_leg_scale
                self.bsdf.plot(context)
                self.bsdf.save(context.scene)
            
            context.area.tag_redraw()
        
        return {'PASS_THROUGH'}
                
    def invoke(self, context, event):
        cao = context.active_object
        if cao and cao.active_material.get('bsdf') and cao.active_material['bsdf']['xml'] and cao.active_material['bsdf']['type'] == ' ':
            width, height = context.region.width, context.region.height
            self.bsdf = bsdf([160, height - 40], width, height, 'bsdf.png', 750, 400)
            self.bsdf.update(context)
            self.bsdfpress, self.bsdfmove, self.bsdfresize = 0, 0, 0
            self._handle_bsdf_disp = bpy.types.SpaceView3D.draw_handler_add(bsdf_disp, (self, context), 'WINDOW', 'POST_PIXEL')
            context.window_manager.modal_handler_add(self)
            context.scene['viparams']['vidisp'] = 'bsdf_panel'
            context.area.tag_redraw()            
            return {'RUNNING_MODAL'}
        else:
            self.report({'ERROR'},"Selected material contains no BSDF information or contains the wrong BSDF type (only Klems is supported)")
            return {'CANCELLED'}
            
    def remove(self, context):
        self.bsdf.plt.close()
        bpy.types.SpaceView3D.draw_handler_remove(self._handle_bsdf_disp, 'WINDOW')
        context.scene['viparams']['vidisp'] = 'bsdf'
        bpy.data.images.remove(self.bsdf.gimage)
        context.area.tag_redraw()
        
class NODE_OT_FileSelect(bpy.types.Operator, io_utils.ImportHelper):
    bl_idname = "node.fileselect"
    bl_label = "Select file"
    filename = ""
    bl_register = True
    bl_undo = True

    def draw(self,context):
        layout = self.layout
        row = layout.row()
        row.label(text="Import {} file with the file browser".format(self.filename), icon='WORLD_DATA')
        row = layout.row()

    def execute(self, context):
        node = bpy.data.node_groups[self.nodeid.split('@')[1]].nodes[self.nodeid.split('@')[0]]
        if self.filepath.split(".")[-1] in self.fextlist:
            if self.nodeprop == 'epwname':
                node.epwname = self.filepath
            elif self.nodeprop == 'hdrname':
                node.hdrname = self.filepath
            elif self.nodeprop == 'skyname':
                node.skyname = self.filepath
            elif self.nodeprop == 'mtxname':
                node.mtxname = self.filepath
            elif self.nodeprop == 'resfilename':
                node.resfilename = self.filepath
            elif self.nodeprop == 'idffilename':
                node.idffilename = self.filepath
        if " " in self.filepath:
            self.report({'ERROR'}, "There is a space either in the filename or its directory location. Remove this space and retry opening the file.")
        return {'FINISHED'}

    def invoke(self,context,event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

class NODE_OT_HdrSelect(NODE_OT_FileSelect):
    bl_idname = "node.hdrselect"
    bl_label = "Select HDR/VEC file"
    bl_description = "Select the HDR sky image or vector file"
    filename_ext = ".HDR;.hdr;"
    filter_glob = bpy.props.StringProperty(default="*.HDR;*.hdr;", options={'HIDDEN'})
    nodeprop = 'hdrname'
    filepath = bpy.props.StringProperty(subtype='FILE_PATH', options={'HIDDEN', 'SKIP_SAVE'})
    fextlist = ("HDR", "hdr")
    nodeid = bpy.props.StringProperty()

class NODE_OT_SkySelect(NODE_OT_FileSelect):
    bl_idname = "node.skyselect"
    bl_label = "Select RAD file"
    bl_description = "Select the Radiance sky file"
    filename_ext = ".rad;.RAD;"
    filter_glob = bpy.props.StringProperty(default="*.RAD;*.rad;", options={'HIDDEN'})
    nodeprop = 'skyname'
    filepath = bpy.props.StringProperty(subtype='FILE_PATH', options={'HIDDEN', 'SKIP_SAVE'})
    fextlist = ("RAD", "rad")
    nodeid = bpy.props.StringProperty()

class NODE_OT_MtxSelect(NODE_OT_FileSelect):
    bl_idname = "node.mtxselect"
    bl_label = "Select MTX file"
    bl_description = "Select the matrix file"
    filename_ext = ".MTX;.mtx;"
    filter_glob = bpy.props.StringProperty(default="*.MTX;*.mtx;", options={'HIDDEN'})
    nodeprop = 'mtxname'
    filepath = bpy.props.StringProperty(subtype='FILE_PATH', options={'HIDDEN', 'SKIP_SAVE'})
    fextlist = ("MTX", "mtx")
    nodeid = bpy.props.StringProperty()

class NODE_OT_EpwSelect(bpy.types.Operator, io_utils.ImportHelper):
    bl_idname = "node.epwselect"
    bl_label = "Select EPW file"
    bl_description = "Select the EnergyPlus weather file"
    filename_ext = ".HDR;.hdr;.epw;.EPW;"
    filter_glob = bpy.props.StringProperty(default="*.HDR;*.hdr;*.epw;*.EPW;", options={'HIDDEN'})
    nodeprop = 'epwname'
    filepath = bpy.props.StringProperty(subtype='FILE_PATH', options={'HIDDEN', 'SKIP_SAVE'})
    fextlist = ("epw", "EPW", "HDR", "hdr")
    nodeid = bpy.props.StringProperty()

class NODE_OT_LiExport(bpy.types.Operator, io_utils.ExportHelper):
    bl_idname = "node.liexport"
    bl_label = "LiVi context export"
    bl_description = "Export the scene to the Radiance file format"
    bl_register = True
    bl_undo = False
    nodeid = bpy.props.StringProperty()
#    expcontextdict = {'Basic': 'LiVi Basic', 'Complaince': 'LiVi Compliance', '2': 'LiVi CBDM'}

    def invoke(self, context, event):
        scene = context.scene
        if viparams(self, scene):
            return {'CANCELLED'}
        node = bpy.data.node_groups[self.nodeid.split('@')[1]].nodes[self.nodeid.split('@')[0]]
        scene['viparams']['vidisp'] = ''
        scene['viparams']['viexpcontext'] = 'LiVi {}'.format(node.contextmenu)
        scene['viparams']['connode'] = self.nodeid
              
        if bpy.data.filepath:
            objmode()
            node.preexport()
            node.export(scene, self)
            node.postexport()
            return {'FINISHED'}

class NODE_OT_RadPreview(bpy.types.Operator, io_utils.ExportHelper):
    bl_idname = "node.radpreview"
    bl_label = "LiVi preview"
    bl_description = "Prevew the scene with Radiance"
    bl_register = True
    bl_undo = False
    nodeid = bpy.props.StringProperty()
    
    def modal(self, context, event):
        if event.type == 'TIMER':
            if self.rvurun.poll() is not None: # If finished
                for line in self.rvurun.stderr:
                    logentry(line)
                    if 'view up parallel to view direction' in line.decode():
                        self.report({'ERROR'}, "Camera cannot point directly upwards")
                        self.simnode.run = 0
                        return {'CANCELLED'}
                    elif 'x11' in line.decode():
                        self.report({'ERROR'}, "No X11 display server found. You may need to install XQuartz")
                        self.simnode.run = 0
                        return {'CANCELLED'}
                    elif 'source center' in line.decode():
                        self.report({'ERROR'}, "A light source has concave faces. Use mesh - cleanup - split concave faces")
                        self.simnode.run = 0
                        return {'CANCELLED'}
                    else:
                        self.simnode.run = 0
                        return {'FINISHED'}
                self.simnode.run = 0
                return {'FINISHED'}
            else:           
                return {'PASS_THROUGH'}
        else:
            return {'PASS_THROUGH'}
        

    def invoke(self, context, event):
        scene = context.scene
        if viparams(self, scene):
            return {'CANCELLED'}
        objmode()
        self.simnode, frame = bpy.data.node_groups[self.nodeid.split('@')[1]].nodes[self.nodeid.split('@')[0]], scene.frame_current
        self.simnode.presim()
        scene['liparams']['fs'] = min([c['fs'] for c in (self.simnode['goptions'], self.simnode['coptions'])])
        scene['liparams']['fe'] = max([c['fe'] for c in (self.simnode['goptions'], self.simnode['coptions'])])

        if frame not in range(scene['liparams']['fs'], scene['liparams']['fe'] + 1):
            self.report({'ERROR'}, "Current frame is not within the exported frame range")
            return {'CANCELLED'}
            
        cam = scene.camera
        
        if cam:
            curres = 0.1
            createradfile(scene, frame, self, self.simnode)
            createoconv(scene, frame, self, self.simnode)
            cang = '180 -vth ' if self.simnode['coptions']['Context'] == 'Basic' and self.simnode['coptions']['Type'] == '1' else cam.data.angle*180/pi
            vv = 180 if self.simnode['coptions']['Context'] == 'Basic' and self.simnode['coptions']['Type'] == '1' else cang * scene.render.resolution_y/scene.render.resolution_x
            vd = (0.001, 0, -1*cam.matrix_world[2][2]) if (round(-1*cam.matrix_world[0][2], 3), round(-1*cam.matrix_world[1][2], 3)) == (0.0, 0.0) else [-1*cam.matrix_world[i][2] for i in range(3)]

            if self.simnode.pmap:
                self.pfile = progressfile(scene, datetime.datetime.now(), 100)
                self.kivyrun = progressbar(os.path.join(scene['viparams']['newdir'], 'viprogress'))
                errdict = {'fatal - too many prepasses, no global photons stored\n': "Too many prepasses have ocurred. Make sure light sources can see your geometry",
                'fatal - too many prepasses, no global photons stored, no caustic photons stored\n': "Too many prepasses have ocurred. Turn off caustic photons and encompass the scene",
               'fatal - zero flux from light sources\n': "No light flux, make sure there is a light source and that photon port normals point inwards",
               'fatal - no light sources in distribPhotons\n': "No light sources. Photon mapping does not work with HDR skies",
               'fatal - no valid photon ports found\n': 'Re-export the geometry'}
                amentry, pportentry, cpentry, cpfileentry = retpmap(self.simnode, frame, scene)
                open('{}.pmapmon'.format(scene['viparams']['filebase']), 'w')
                pmcmd = 'mkpmap -t 20 -e {1}.pmapmon -fo+ -bv+ -apD 0.001 {0} -apg {1}-{2}.gpm {3} {4} {5} {1}-{2}.oct'.format(pportentry, scene['viparams']['filebase'], frame, self.simnode.pmapgno, cpentry, amentry)
                print(pmcmd)
                pmrun = Popen(pmcmd.split(), stderr = PIPE, stdout = PIPE)

                while pmrun.poll() is None:   
                    sleep(10)
                    with open('{}.pmapmon'.format(scene['viparams']['filebase']), 'r') as vip:
                        for line in vip.readlines()[::-1]:
                            if '%' in line:
                                curres = float(line.split()[6][:-2])
                                break
                                
                    if self.pfile.check(curres) == 'CANCELLED': 
                        pmrun.kill()                                   
                        return {'CANCELLED'}
                
                if self.kivyrun.poll() is None:
                    self.kivyrun.kill()
                        
                with open('{}.pmapmon'.format(scene['viparams']['filebase']), 'r') as pmapfile:
                    for line in pmapfile.readlines():
                        if line in errdict:
                            logentry(line)
                            self.report({'ERROR'}, errdict[line])
                            return {'CANCELLED'}
                                        
                rvucmd = "rvu -w -ap {8} 50 {9} -n {0} -vv {1:.3f} -vh {2} -vd {3[0]:.3f} {3[1]:.3f} {3[2]:.3f} -vp {4[0]:.3f} {4[1]:.3f} {4[2]:.3f} -vu {10[0]:.3f} {10[1]:.3f} {10[2]:.3f} {5} {6}-{7}.oct".format(scene['viparams']['wnproc'], vv, cang, vd, cam.location, self.simnode['radparams'], scene['viparams']['filebase'], scene.frame_current, '{}-{}.gpm'.format(scene['viparams']['filebase'], frame), cpfileentry, cam.matrix_world.to_quaternion() * mathutils.Vector((0, 1, 0)))
                
            else:
                rvucmd = "rvu -w -n {0} -vv {1} -vh {2} -vd {3[0]:.3f} {3[1]:.3f} {3[2]:.3f} -vp {4[0]:.3f} {4[1]:.3f} {4[2]:.3f} -vu {8[0]:.3f} {8[1]:.3f} {8[2]:.3f} {5} {6}-{7}.oct".format(scene['viparams']['wnproc'], vv, cang, vd, cam.location, self.simnode['radparams'], scene['viparams']['filebase'], scene.frame_current, cam.matrix_world.to_quaternion() * mathutils.Vector((0, 1, 0)))

            self.rvurun = Popen(rvucmd.split(), stdout = PIPE, stderr = PIPE)
            self.simnode.run = 1
            wm = context.window_manager
            self._timer = wm.event_timer_add(5, context.window)
            wm.modal_handler_add(self)
            return {'RUNNING_MODAL'}

#            for line in rvurun.stderr:
#                print(line)
#                if 'view up parallel to view direction' in line.decode():
#                    self.report({'ERROR'}, "Camera cannot point directly upwards")
#                    return {'CANCELLED'}
#                elif 'x11' in line.decode():
#                    self.report({'ERROR'}, "No X11 display server found. You may need to install XQuartz")
#                    return {'CANCELLED'}
#                elif 'source center' in line.decode():
#                    self.report({'ERROR'}, "A light source has concave faces. Use mesh - cleanup - split concave faces")
#                    return {'CANCELLED'}
#                
#            return {'FINISHED'}
        else:
            self.report({'ERROR'}, "There is no camera in the scene. Radiance preview will not work")
            return {'CANCELLED'}

class NODE_OT_RadImage(bpy.types.Operator):
    bl_idname = "node.radimage"
    bl_label = "LiVi Image"
    bl_description = "Generate an image with Rpict"
    bl_register = True
    bl_undo = False
    nodeid = bpy.props.StringProperty()

    def modal(self, context, event):
        if event.type == 'TIMER':
            if self.rprun.poll() is not None: # If finished
                for line in self.rprun.stderr:
                    logentry(line)
                    if 'view up parallel to view direction' in line.decode():
                        self.report({'ERROR'}, "Camera cannot point directly upwards")
                        return {'CANCELLED'}
                    elif 'x11' in line.decode():
                        self.report({'ERROR'}, "No X11 display server found. You may need to install XQuartz")
                        return {'CANCELLED'}
                    elif 'source center' in line.decode():
                        self.report({'ERROR'}, "A light source has concave faces. Use mesh - cleanup - split concave faces")
                        return {'CANCELLED'}
                
                if self.frame > self.scene['liparams']['fe']:
                    self.simnode['frames'] = [f for f in range(self.scene['liparams']['fs'], self.scene['liparams']['fe'] + 1)]
                    return {self.terminate()}
                            
                elif self.frame > self.frameold:
                    self.percent = (self.frame - self.scene['liparams']['fs']) * 100
                    self.frameold = self.frame
                    os.remove(self.rpictfile)
                    if self.simnode.pmap:
                        amentry, pportentry, cpentry, cpfileentry = retpmap(self.simnode, self.frame, self.scene)
                        pmcmd = ('mkpmap -bv+ +fo -apD 0.001 {0} -apg {1}-{2}.gpm {3} {4} {5} {1}-{2}.oct'.format(pportentry, self.scene['viparams']['filebase'], self.frame, self.simnode.pmapgno, cpentry, amentry))                   
                        pmrun = Popen(pmcmd.split(), stderr = PIPE)
                        for line in pmrun.stderr: 
                            logentry('Photon map error: {}'.format(line.decode))#        draw_image(self, self.ydiff * 0.1)
                            
                            if line.decode() in self.errdict:
                                
                                self.report({'ERROR'}, self.errdict[line.decode()])
                                return {'CANCELLED'}
                        rpictcmd = "rpict -w -e {7} -t 10 -vth -vh 180 -vv 180 -x 800 -y 800 -vd {0[0][2]:.3f} {0[1][2]} {0[2][2]} -vp {1[0]} {1[1]} {1[2]} -vu {8[0]} {8[1]} {8[2]} {2} -ap {5} 50 {6} {3}-{4}.oct".format(-1*self.cam.matrix_world, self.cam.location, self.simnode['radparams'], self.scene['viparams']['filebase'], self.frame, '{}-{}.gpm'.format(self.scene['viparams']['filebase'], self.frame), cpfileentry, self.rpictfile, self.cam.matrix_world.to_quaternion() * mathutils.Vector((0, 1, 0)))
                    else:
                        rpictcmd = "rpict -w -e {5} -t 10 -vth -vh 180 -vv 180 -x 800 -y 800 -vd {0[0][2]} {0[1][2]} {0[2][2]} -vp {1[0]} {1[1]} {1[2]} -vu {6[0]} {6[1]} {6[2]} {2} {3}-{4}.oct".format(-1*self.cam.matrix_world, self.cam.location, self.simnode['radparams'], self.scene['viparams']['filebase'], self.frame, self.rpictfile, self.cam.matrix_world.to_quaternion() * mathutils.Vector((0, 1, 0)))
                    self.rprun = Popen(rpictcmd.split(), stdout = PIPE)                    
                    return {'RUNNING_MODAL'}  
                self.frame += 1
                return {'RUNNING_MODAL'}
            else:
                with open(self.rpictfile, 'r') as rpictfile:
                    for line in rpictfile.readlines()[::-1]:
                        if '%' in line:
                            for lineentry in line.split():
                                if '%' in lineentry:
                                    self.percent = (float(lineentry.strip('%')) + (self.frame - self.scene['liparams']['fs']) * 100)/self.frames
                            break
     
                if self.percent:
                    if self.pfile.check(self.percent) == 'CANCELLED':                                    
                        return {self.terminate()}
                
                return {'PASS_THROUGH'}
        else:
            return {'PASS_THROUGH'}
            
    def terminate(self):
        nodecolour(self.simnode, 0)
        self.kivyrun.kill() 
        self.simnode.run = 0

        if self.rprun.poll() == None:                          
            self.rprun.kill()
       
        self.simnode.postsim()
        return 'FINISHED'

    def execute(self, context):        
        self.scene = bpy.context.scene
        self.cam = self.scene.camera
        
        if self.cam:
            self.percent = 0
            self.reslists = []
            self.res = []
            self.rpictfile = os.path.join(self.scene['viparams']['newdir'], 'rpictprogress')
            self.simnode = bpy.data.node_groups[self.nodeid.split('@')[1]].nodes[self.nodeid.split('@')[0]]
            self.simnode.presim()
            self.simnode.run = 1
            nodecolour(self.simnode, 1)
            self.scene['liparams']['fs'] = min([c['fs'] for c in (self.simnode['goptions'], self.simnode['coptions'])])
            self.scene['liparams']['fe'] = max([c['fe'] for c in (self.simnode['goptions'], self.simnode['coptions'])])
            self.frames = self.scene['liparams']['fe'] - self.scene['liparams']['fs'] + 1
            self.frame = self.scene['liparams']['fs']
            self.frameold = self.frame
            cang = self.cam.data.angle*180/pi
      
            vv = cang * self.simnode.y/self.simnode.x
            vd = (0.001, 0, -1*self.cam.matrix_world[2][2]) if (round(-1*self.cam.matrix_world[0][2], 3), round(-1*self.cam.matrix_world[1][2], 3)) == (0.0, 0.0) else [-1*self.cam.matrix_world[i][2] for i in range(3)]

            for frame in range(self.scene['liparams']['fs'], self.scene['liparams']['fe'] + 1):
                createradfile(self.scene, frame, self, self.simnode)
                createoconv(self.scene, frame, self, self.simnode)
            if self.simnode.pmap:
                self.errdict = {'fatal - too many prepasses, no global photons stored\n': "Too many prepasses have ocurred. Make sure light sources can see your geometry",
                'fatal - too many prepasses, no global photons stored, no caustic photons stored\n': "Too many prepasses have ocurred. Turn off caustic photons and encompass the scene",
               'fatal - zero flux from light sources\n': "No light flux, make sure there is a light source and that photon port normals point inwards",
               'fatal - no light sources\n': "No light sources. Photon mapping does not work with HDR skies",
               'fatal - failed photon distribution\n': "failed photon distribution"}
                amentry, pportentry, cpentry, cpfileentry = retpmap(self.simnode, self.frame, self.scene)
                pmcmd = ('mkpmap -bv+ +fo -apD 0.001 {0} -apg {1}-{2}.gpm {3} {4} {5} {1}-{2}.oct'.format(pportentry, self.scene['viparams']['filebase'], self.frame, self.simnode.pmapgno, cpentry, amentry))                   
                pmrun = Popen(pmcmd.split(), stderr = PIPE)
                for line in pmrun.stderr: 
                    logentry('Photon map message: {}'.format(line.decode()))
                    if line.decode() in self.errdict:
                        self.report({'ERROR'}, self.errdict[line.decode()])
                        self.simnode.postsim()
                        return {'CANCELLED'}

                rpictcmd = "rpict -t 5 -e {14} -x {9} -y {10} {11} -vv {1:.3f} -vh {2:.3f} -vd {3[0]:.3f} {3[1]:.3f} {3[2]:.3f} -vp {4[0]:.3f} {4[1]:.3f} {4[2]:.3f} -vu {15[0]:.3f} {15[1]:.3f} {15[2]:.3f} {5} -ap {12} 50 {13} {5} {6}-{7}.oct > {8}".format('', 
                                          vv, 
                                          cang, 
                                          vd, 
                                          self.cam.location, 
                                          self.simnode['radparams'], 
                                          self.scene['viparams']['filebase'], 
                                            self.frame, 
                                            self.simnode.hdrname, 
                                            self.simnode.x, 
                                            self.simnode.y, 
                                            ('', '-i')[self.simnode.illu], 
                                            '{}-{}.gpm'.format(self.scene['viparams']['filebase'], self.frame), 
                                             cpfileentry, 
                                             self.rpictfile, 
                                             self.cam.matrix_world.to_quaternion() * mathutils.Vector((0, 1, 0)))
            else:
                rpictcmd = "rpict -t 5 -e {12} -x {9} -y {10} {11} -vv {1:.3f} -vh {2:.3f} -vd {3[0]:.3f} {3[1]:.3f} {3[2]:.3f} -vp {4[0]:.3f} {4[1]:.3f} {4[2]:.3f}  -vu {13[0]:.3f} {13[1]:.3f} {13[2]:.3f} {5} {6}-{7}.oct > {8}".format('', 
                                          vv, 
                                          cang, 
                                          vd, 
                                          self.cam.location, 
                                          self.simnode['radparams'], 
                                            self.scene['viparams']['filebase'], 
                                            self.scene.frame_current, 
                                            self.simnode.hdrname, 
                                            self.simnode.x, 
                                            self.simnode.y, 
                                            ('', '-i')[self.simnode.illu], 
                                            self.rpictfile, 
                                            self.cam.matrix_world.to_quaternion() * mathutils.Vector((0, 1, 0)))
            logentry('rpict command: {}'.format(rpictcmd))
            self.starttime = datetime.datetime.now()
            self.pfile = progressfile(self.scene, datetime.datetime.now(), 100)
            self.kivyrun = progressbar(os.path.join(self.scene['viparams']['newdir'], 'viprogress'))
            self.rprun = Popen(rpictcmd, stdout=PIPE, stderr = PIPE, shell = True)
            wm = context.window_manager
            self._timer = wm.event_timer_add(5, context.window)
            wm.modal_handler_add(self)
            return {'RUNNING_MODAL'}
        else:
            self.report({'ERROR'}, "There is no camera in the scene. Create one for glare analysis")
            return {'FINISHED'}

class NODE_OT_LiFC(bpy.types.Operator):            
    bl_idname = "node.livifc"
    bl_label = "LiVi False Colour Image"
    bl_description = "False colour an image with falsecolor"
    bl_register = True
    bl_undo = False
    nodeid = bpy.props.StringProperty()

    def execute(self, context):
        fcnode = bpy.data.node_groups[self.nodeid.split('@')[1]].nodes[self.nodeid.split('@')[0]] 
#        if fcnode.inputs['Image'].links:
        imnode = fcnode.inputs['Image'].links[0].from_node 
                              
        if not os.path.isfile(imnode.hdrname):
            self.report({'ERROR'}, "The original image file is not valid")
            return {'CANCELLED'} 
        lmax = '-s {}'.format(fcnode.lmax) if fcnode.lmax else '-s a'
        scaling = '' if fcnode.nscale == '0' else '-log {}'.format(fcnode.decades) 
        mult = '-m {}'.format(fcnode.unitmult[fcnode.unit]) 
        legend = '-l {} -lw {} -lh {} {} {} {}'.format(fcnode.unitdict[fcnode.unit], fcnode.lw, fcnode.lh, lmax, scaling, mult) if fcnode.legend else ''
        bands = '-cb' if fcnode.bands else ''
        contour = '-cl {}'.format(bands) if fcnode.contour else ''
        poverlay = '-ip' if fcnode.contour and fcnode.overlay else '-i'
        fccmd = 'falsecolor {} {} -pal {} {} {}'.format(poverlay, imnode.hdrname, fcnode.coldict[fcnode.colour], legend, contour, fcnode.hdrname)
        with open(fcnode.hdrname, 'w') as fcfile:
            Popen(fccmd.split(), stdout=fcfile, stderr = PIPE).wait()  
        if 'fc.hdr' not in bpy.data.images:
            im = bpy.data.images.load(fcnode.hdrname)
            im.name = 'fc.hdr'
        else:
            bpy.data.images['fc.hdr'].reload()
            bpy.data.images['fc.hdr'].name = 'fc.hdr'
                                       
        return {'FINISHED'}
        
class NODE_OT_LiViCalc(bpy.types.Operator):
    bl_idname = "node.livicalc"
    bl_label = "LiVi simulation"
    nodeid = bpy.props.StringProperty()
    bl_register = True
    bl_undo = False

    def invoke(self, context, event):
        scene = context.scene
        if viparams(self, scene):
            return {'CANCELLED'}
                    
        objmode()
        clearscene(scene, self)
        simnode = bpy.data.node_groups[self.nodeid.split('@')[1]].nodes[self.nodeid.split('@')[0]]
        simnode.presim()
        contextdict = {'Basic': 'LiVi Basic', 'Compliance': 'LiVi Compliance', 'CBDM': 'LiVi CBDM'}        
        
        # Set scene parameters
        scene['viparams']['visimcontext'] = contextdict[simnode['coptions']['Context']]
        scene['liparams']['fs'] = min((simnode['coptions']['fs'], simnode['goptions']['fs'])) 
        scene['liparams']['fe'] = max((simnode['coptions']['fe'], simnode['goptions']['fe'])) 
        scene['liparams']['cp'] = simnode['goptions']['cp']
        scene['liparams']['unit'] = simnode['coptions']['unit']
        scene['liparams']['type'] = simnode['coptions']['Type']
        scene['viparams']['vidisp'] = ''
        scene.frame_start, scene.frame_end = scene['liparams']['fs'], scene['liparams']['fe']
        
        simnode.sim(scene)

        for frame in range(scene['liparams']['fs'], scene['liparams']['fe'] + 1):
            if createradfile(scene, frame, self, simnode) == 'CANCELLED' or createoconv(scene, frame, self, simnode) == 'CANCELLED':
                return {'CANCELLED'}
        
        calcout = li_calc(self, simnode, livisimacc(simnode))

        if calcout == 'CANCELLED':
            return {'CANCELLED'}
        else:
            simnode['reslists'] = calcout
        if simnode['coptions']['Context'] != 'CBDM' and simnode['coptions']['Context'] != '1':
            scene.vi_display = 1

        scene['viparams']['vidisp'] = 'li'
        scene['viparams']['resnode'] = simnode.name
        scene['viparams']['restree'] = self.nodeid.split('@')[1]
        simnode.postsim()
        self.report({'INFO'},"Simulation is finished")
        return {'FINISHED'}
        
class NODE_OT_LiVIGlare(bpy.types.Operator):
    bl_idname = "node.liviglare"
    bl_label = "LiVi glare"
    bl_description = "Create a glare fisheye image from the Blender camera perspective"
    bl_register = True
    bl_undo = False
    nodeid = bpy.props.StringProperty()

    def modal(self, context, event):
        if event.type == 'TIMER':
            if self.egrun.poll() is not None: # If finished
                if self.frame > self.scene['liparams']['fe']:
                    self.reslists += [['All', 'Frames', '', 'Frames', ' '.join([str(f) for f in range(self.scene['liparams']['fs'], self.scene['liparams']['fe'] + 1)])]] + [['All', 'Camera', self.cam.name, ('DGP', 'DGI', 'UGR', 'VCP', 'CGI', 'LV')[ri], ' '.join([str(res) for res in r])] for ri, r in enumerate(zip(*self.res))]
                    self.simnode['reslists'] = self.reslists
                    self.simnode['frames'] = [f for f in range(self.scene['liparams']['fs'], self.scene['liparams']['fe'] + 1)]
                    return {self.terminate()}
                elif self.frame > self.frameold:
                    self.percent = (self.frame - self.scene['liparams']['fs']) * 100
                    self.frameold = self.frame
                    os.remove(self.rpictfile)
                    if self.simnode.pmap:
                        amentry, pportentry, cpentry, cpfileentry = retpmap(self.simnode, self.frame, self.scene)
                        pmcmd = ('mkpmap -bv+ +fo -apD 0.001 {0} -apg {1}-{2}.gpm {3} {4} {5} {1}-{2}.oct'.format(pportentry, self.scene['viparams']['filebase'], self.frame, self.simnode.pmapgno, cpentry, amentry))                   
                        pmrun = Popen(pmcmd.split(), stderr = PIPE)
                        for line in pmrun.stderr: 
                            print('pmrun', line)#        draw_image(self, self.ydiff * 0.1)
                            if line.decode() in self.errdict:
                                self.report({'ERROR'}, self.errdict[line.decode()])
                                return {'CANCELLED'}
                        rpictcmd = "rpict -w -e {7} -t 10 -vth -vh 180 -vv 180 -x 800 -y 800 -vd {0[0][2]:.3f} {0[1][2]} {0[2][2]} -vp {1[0]} {1[1]} {1[2]} {2} -ap {5} 50 {6} {3}-{4}.oct".format(-1*self.cam.matrix_world, self.cam.location, self.simnode['radparams'], self.scene['viparams']['filebase'], self.frame, '{}-{}.gpm'.format(self.scene['viparams']['filebase'], self.frame), cpfileentry, self.rpictfile)
                    else:
                        rpictcmd = "rpict -w -e {5} -t 10 -vth -vh 180 -vv 180 -x 800 -y 800 -vd {0[0][2]} {0[1][2]} {0[2][2]} -vp {1[0]} {1[1]} {1[2]} {2} {3}-{4}.oct".format(-1*self.cam.matrix_world, self.cam.location, self.simnode['radparams'], self.scene['viparams']['filebase'], self.frame, self.rpictfile)
                    self.rprun = Popen(rpictcmd.split(), stdout = PIPE)                    
                    self.egcmd = 'evalglare {} -c {}'.format(('-u 1 0 0', '')[sys.platform == 'win32'], os.path.join(self.scene['viparams']['newdir'], 'glare{}.hdr'.format(self.frame)))                    
                    self.egrun = Popen(self.egcmd.split(), stdin = self.rprun.stdout, stdout = PIPE)
                    return {'RUNNING_MODAL'}

                time = datetime.datetime(2014, 1, 1, self.simnode['coptions']['shour'], 0) + datetime.timedelta(self.simnode['coptions']['sdoy'] - 1) if self.simnode['coptions']['anim'] == '0' else \
                    datetime.datetime(2014, 1, 1, int(self.simnode['coptions']['shour']), int(60*(self.simnode['coptions']['shour'] - int(self.simnode['coptions']['shour'])))) + datetime.timedelta(self.simnode['coptions']['sdoy'] - 1) + datetime.timedelta(hours = int(self.simnode['coptions']['interval']*(self.frame-self.scene['liparams']['fs'])), seconds = int(60*(self.simnode['coptions']['interval']*(self.frame-self.scene['liparams']['fs']) - int(self.simnode['coptions']['interval']*(self.frame-self.scene['liparams']['fs'])))))
                with open(self.scene['viparams']['filebase']+".glare", "w") as glaretf:
                    for line in self.egrun.stdout:
                        if line.decode().split(",")[0] == 'dgp':                            
                            glaretext = line.decode().replace(',', ' ').replace("#INF", "").split(' ')
                            res = [float(x) for x in glaretext[6:12]]
                            glaretf.write("{0:0>2d}/{1:0>2d} {2:0>2d}:{3:0>2d}\ndgp: {4:.2f}\ndgi: {5:.2f}\nugr: {6:.2f}\nvcp: {7:.2f}\ncgi: {8:.2f}\nLv: {9:.0f}\n".format(time.day, time.month, time.hour, time.minute, *res))
                            self.res.append(res)
                            self.reslists += [[str(self.frame), 'Camera', self.cam.name, 'DGP', '{0[0]}'.format(res)], [str(self.frame), 'Camera', self.cam.name, 'DGI', '{0[1]}'.format(res)], [str(self.frame), 'Camera', self.cam.name, 'UGR', '{0[2]}'.format(res)], [str(self.frame), 'Camera', self.cam.name, 'VCP', '{0[3]}'.format(res)], [str(self.frame), 'Camera', self.cam.name, 'CGI', '{[4]}'.format(res)], [str(self.frame), 'Camera', self.cam.name, 'LV', '{[5]}'.format(res)]]
                
                pcondcmd = "pcond -u 300 {0}.hdr".format(os.path.join(self.scene['viparams']['newdir'], 'glare'+str(self.frame)))
                with open('{}.temphdr'.format(os.path.join(self.scene['viparams']['newdir'], 'glare'+str(self.frame))), 'w') as temphdr:
                    Popen(pcondcmd.split(), stdout = temphdr).communicate()
                catcmd = "{0} {1}.glare".format(self.scene['viparams']['cat'], self.scene['viparams']['filebase'])
                catrun = Popen(catcmd, stdout = PIPE, shell = True)
                psigncmd = "psign -h 32 -cb 0 0 0 -cf 40 40 40"
                psignrun = Popen(psigncmd.split(), stdin = catrun.stdout, stdout = PIPE)
                pcompcmd = "pcompos {0}.temphdr 0 0 - 800 550".format(os.path.join(self.scene['viparams']['newdir'], 'glare'+str(self.frame)))
                with open("{}.hdr".format(os.path.join(self.scene['viparams']['newdir'], 'glare'+str(self.frame))), 'w') as ghdr:
                    Popen(pcompcmd.split(), stdin = psignrun.stdout, stdout = ghdr).communicate()
                os.remove(os.path.join(self.scene['viparams']['newdir'], 'glare{}.temphdr'.format(self.frame)))

                if 'glare{}.hdr'.format(self.frame) in bpy.data.images:
                    bpy.data.images['glare{}.hdr'.format(self.frame)].filepath = os.path.join(self.scene['viparams']['newdir'], 'glare{}.hdr'.format(self.frame))
                    bpy.data.images['glare{}.hdr'.format(self.frame)].reload()
                else:
                    bpy.data.images.load(os.path.join(self.scene['viparams']['newdir'], 'glare{}.hdr'.format(self.frame)))
                self.frame += 1
                return {'RUNNING_MODAL'}
            else:
                with open(self.rpictfile) as rpictfile:
                    for line in rpictfile.readlines()[::-1]:
                        if '%' in line:
                            for lineentry in line.split():
                                if '%' in lineentry:
                                    self.percent = (float(lineentry.strip('%')) + (self.frame - self.scene['liparams']['fs']) * 100)/self.frames
                            break
     
                if self.percent:
                    if self.pfile.check(self.percent) == 'CANCELLED':                                    
                        return {self.terminate()}
                
                return {'PASS_THROUGH'}
        else:
            return {'PASS_THROUGH'}
            
    def terminate(self):
        nodecolour(self.simnode, 0)
        self.kivyrun.kill() 
        self.simnode.run = 0

        if self.egrun.poll() == None:                          
            self.egrun.kill()
            
        self.rprun.kill()        
        self.simnode.postsim()
        return 'FINISHED'

    def execute(self, context):        
        self.scene = bpy.context.scene
        self.cam = self.scene.camera
        
        if self.cam:
            self.percent = 0
            self.reslists = []
            self.res = []
            self.rpictfile = os.path.join(self.scene['viparams']['newdir'], 'rpictprogress')
            self.simnode = bpy.data.node_groups[self.nodeid.split('@')[1]].nodes[self.nodeid.split('@')[0]]
            self.simnode.presim()
            self.simnode.run = 1
            nodecolour(self.simnode, 1)
            self.scene['liparams']['fs'] = min([c['fs'] for c in (self.simnode['goptions'], self.simnode['coptions'])])
            self.scene['liparams']['fe'] = max([c['fe'] for c in (self.simnode['goptions'], self.simnode['coptions'])])
            self.frames = self.scene['liparams']['fe'] - self.scene['liparams']['fs'] + 1
            self.frame = self.scene['liparams']['fs']
            self.frameold = self.frame
            for frame in range(self.scene['liparams']['fs'], self.scene['liparams']['fe'] + 1):
                createradfile(self.scene, frame, self, self.simnode)
                createoconv(self.scene, frame, self, self.simnode)
            if self.simnode.pmap:
                self.errdict = {'fatal - too many prepasses, no global photons stored\n': "Too many prepasses have ocurred. Make sure light sources can see your geometry",
                'fatal - too many prepasses, no global photons stored, no caustic photons stored\n': "Too many prepasses have ocurred. Turn off caustic photons and encompass the scene",
               'fatal - zero flux from light sources\n': "No light flux, make sure there is a light source and that photon port normals point inwards",
               'fatal - no light sources\n': "No light sources. Photon mapping does not work with HDR skies"}
                amentry, pportentry, cpentry, cpfileentry = retpmap(self.simnode, self.frame, self.scene)
                pmcmd = ('mkpmap -bv+ +fo -apD 0.001 {0} -apg {1}-{2}.gpm {3} {4} {5} {1}-{2}.oct'.format(pportentry, self.scene['viparams']['filebase'], self.frame, self.simnode.pmapgno, cpentry, amentry))                   
                pmrun = Popen(pmcmd.split(), stderr = PIPE)
                for line in pmrun.stderr: 
                    logentry(line)
                    if line.decode() in self.errdict:
                        self.report({'ERROR'}, self.errdict[line.decode()])
                        return {'FINISHED'}
                rpictcmd = "rpict -w -e {7} -t 1 -vth -vh 180 -vv 180 -x 800 -y 800 -vd {0[0][2]:.3f} {0[1][2]} {0[2][2]} -vp {1[0]} {1[1]} {1[2]} {2} -ap {5} 50 {6} {3}-{4}.oct".format(-1*self.cam.matrix_world, self.cam.location, self.simnode['radparams'], self.scene['viparams']['filebase'], self.frame, '{}-{}.gpm'.format(self.scene['viparams']['filebase'], self.frame), cpfileentry, self.rpictfile)
            else:
                rpictcmd = "rpict -w -vth -vh 180 -e {5} -t 1 -vv 180 -x 800 -y 800 -vd {0[0][2]:.3f} {0[1][2]} {0[2][2]} -vp {1[0]} {1[1]} {1[2]} {2} {3}-{4}.oct".format(-1*self.cam.matrix_world, self.cam.location, self.simnode['radparams'], self.scene['viparams']['filebase'], self.frame, self.rpictfile)

            self.starttime = datetime.datetime.now()
            self.pfile = progressfile(self.scene, datetime.datetime.now(), 100)
            self.kivyrun = progressbar(os.path.join(self.scene['viparams']['newdir'], 'viprogress'))
            self.rprun = Popen(rpictcmd.split(), stdout=PIPE, stderr = PIPE)
            egcmd = "evalglare {} -c {}".format(('-u 1 0 0', '')[sys.platform == 'win32'], os.path.join(self.scene['viparams']['newdir'], 'glare{}.hdr'.format(self.frame)))
            self.egrun = Popen(egcmd.split(), stdin = self.rprun.stdout, stdout=PIPE, stderr = PIPE)
            wm = context.window_manager
            self._timer = wm.event_timer_add(10, context.window)
            wm.modal_handler_add(self)
            return {'RUNNING_MODAL'}
        else:
            self.report({'ERROR'}, "There is no camera in the scene. Create one for glare analysis")
            return {'FINISHED'}

class IES_Select(bpy.types.Operator, io_utils.ImportHelper):
    bl_idname = "livi.ies_select"
    bl_label = "Select IES file"
    bl_description = "Select the lamp IES file"
    filename = ""
    filename_ext = ".ies; .IES"
    filter_glob = bpy.props.StringProperty(default="*.ies; *.IES", options={'HIDDEN'})
    bl_register = True
    bl_undo = True

    def draw(self,context):
        layout = self.layout
        row = layout.row()
        row.label(text="Open an IES File with the file browser", icon='WORLD_DATA')

    def execute(self, context):
        lamp = bpy.context.active_object
#        if " " not in self.filepath:
        lamp['ies_name'] = self.filepath
        return {'FINISHED'}
#        else:
#            self.report({'ERROR'}, "There is a space either in the IES filename or directory location. Rename or move the file.")
#            lamp['ies_name'] = self.filepath
#            return {'CANCELLED'}

    def invoke(self,context,event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

class NODE_OT_ESOSelect(NODE_OT_FileSelect):
    bl_idname = "node.esoselect"
    bl_label = "Select EnVi results file"
    bl_description = "Select the EnVi results file to process"
    filename_ext = ".eso"
    filter_glob = bpy.props.StringProperty(default="*.eso", options={'HIDDEN'})
    nodeprop = 'resfilename'
    filepath = bpy.props.StringProperty(subtype='FILE_PATH', options={'HIDDEN', 'SKIP_SAVE'})
    fextlist = ("eso")
    nodeid = bpy.props.StringProperty()

class NODE_OT_IDFSelect(NODE_OT_FileSelect):
    bl_idname = "node.idfselect"
    bl_label = "Select EnergyPlus input file"
    bl_description = "Select the EnVi input file to process"
    filename_ext = ".idf"
    filter_glob = bpy.props.StringProperty(default="*.idf", options={'HIDDEN'})
    nodeprop = 'idffilename'
    filepath = bpy.props.StringProperty(subtype='FILE_PATH', options={'HIDDEN', 'SKIP_SAVE'})
    fextlist = ("idf")
    nodeid = bpy.props.StringProperty()

class NODE_OT_ASCImport(bpy.types.Operator, io_utils.ImportHelper):
    bl_idname = "node.ascimport"
    bl_label = "Select ESRI Grid file"
    bl_description = "Select the ESRI Grid file to process"
    filename = ""
    filename_ext = ".asc"
    filter_glob = bpy.props.StringProperty(default="*.asc", options={'HIDDEN'})
    bl_register = True
    bl_undo = False
    nodeid = bpy.props.StringProperty()

    def draw(self,context):
        layout = self.layout
        row = layout.row()
        row.label(text="Open an asc file with the file browser", icon='WORLD_DATA')

    def execute(self, context):
        node = bpy.data.node_groups[self.nodeid.split('@')[1]].nodes[self.nodeid.split('@')[0]]
        startxs, startys, vpos, faces, vlen = [], [], [], [], 0
        ascfiles = [self.filepath] if node.single else [os.path.join(os.path.dirname(os.path.realpath(self.filepath)), file) for file in os.listdir(os.path.dirname(os.path.realpath(self.filepath))) if file.endswith('.asc')]

        for file in ascfiles:
            with open(file, 'r') as ascfile:
                lines = ascfile.readlines()
                [startx, starty] = [eval(lines[i].split()[1]) for i in (2, 3)]
                startxs.append(startx)
                startys.append(starty)
        minstartx,  minstarty = min(startxs), min(startys)

        for file in ascfiles:
            with open(file, 'r') as ascfile:
                lines = ascfile.readlines()
                (vpos, faces) = [[], []] if node.splitmesh else [vpos, faces]
                xy = [eval(lines[i].split()[1]) for i in (2, 3)]
                [ostartx, ostarty] = xy
                [mstartx, mstarty] = [0, 0] if node.splitmesh else xy
                [cols, rows, size, nodat] = [eval(lines[i].split()[1]) for i in (0, 1, 4, 5)]
                vpos += [(mstartx + (size * ci), mstarty + (size * (rows - ri)), (float(h), 0)[h == nodat]) for ri, height in enumerate([line.split() for line in lines[6:]]) for ci, h in enumerate(height)]
                faces += [(i+1, i, i+rows, i+rows + 1) for i in range((vlen, 0)[node.splitmesh], len(vpos)-cols) if (i+1)%cols]
                vlen += cols*rows

                if node.splitmesh or file == ascfiles[-1]:
                    (basename, vpos) = (file.split(os.sep)[-1].split('.')[0], vpos) if node.splitmesh else ('Terrain', [(v[0] - minstartx, v[1] - minstarty, v[2]) for v in vpos])
                    me = bpy.data.meshes.new("{} mesh".format(basename))
                    bm = bmesh.new()
                    [bm.verts.new(vco) for vco in vpos]
                    bm.verts.ensure_lookup_table()
                    [bm.faces.new([bm.verts[fv] for fv in face]) for face in faces]
                    bmesh.ops.delete(bm, geom = [v for v in bm.verts if v.co[2] < -900], context = 1)
                    bm.to_mesh(me)
                    me.update()
                    ob = bpy.data.objects.new(basename, me)
                    ob.location = (ostartx - minstartx, ostarty - minstarty, 0) if node.splitmesh else (0, 0, 0)   # position object at 3d-cursor
                    bpy.context.scene.objects.link(ob)
                    bm.free()
        vpos, faces = [], []
        return {'FINISHED'}

    def invoke(self,context,event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

class NODE_OT_CSVExport(bpy.types.Operator, io_utils.ExportHelper):
    bl_idname = "node.csvexport"
    bl_label = "Export a CSV file"
    bl_description = "Select the CSV file to export"
    filename = "results"
    filename_ext = ".csv"
    filter_glob = bpy.props.StringProperty(default="*.csv", options={'HIDDEN'})
    bl_register = True
    bl_undo = True
    nodeid = bpy.props.StringProperty()

    def draw(self,context):
        layout = self.layout
        row = layout.row()
        row.label(text="Specify the CSV export file with the file browser", icon='WORLD_DATA')

    def execute(self, context):
        node = bpy.data.node_groups[self.nodeid.split('@')[1]].nodes[self.nodeid.split('@')[0]]
        resstring = ''
        resnode = bpy.data.node_groups[self.nodeid.split('@')[1]].nodes[self.nodeid.split('@')[0]].inputs['Results in'].links[0].from_node
        rl = resnode['reslists']
        zrl = list(zip(*rl))

        if len(set(zrl[0])) > 1 and node.animated:
            resstring = ''.join(['{} {},'.format(r[2], r[3]) for r in rl if r[0] == 'All']) + '\n'
            metriclist = list(zip(*[r.split() for ri, r in enumerate(zrl[4]) if zrl[0][ri] == 'All']))
        else:
            resstring = ''.join(['{} {} {},'.format(r[0], r[2], r[3]) for r in rl if r[0] != 'All']) + '\n'
            metriclist = list(zip(*[r.split() for ri, r in enumerate(zrl[4]) if zrl[0][ri] != 'All']))

        for ml in metriclist:
            resstring += ''.join(['{},'.format(m) for m in ml]) + '\n'

        resstring += '\n'

        with open(self.filepath, 'w') as csvfile:
            csvfile.write(resstring)
        return {'FINISHED'}

    def invoke(self,context,event):
        if self.filepath.split('.')[-1] not in ('csv', 'CSV'):
            self.filepath = os.path.join(context.scene['viparams']['newdir'], context.scene['viparams']['filebase'] + '.csv')            
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

class NODE_OT_TextUpdate(bpy.types.Operator):
    bl_idname = "node.textupdate"
    bl_label = "Update a text file"
    bl_description = "Update a text file"

    nodeid = bpy.props.StringProperty()

    def execute(self, context):
        tenode = bpy.data.node_groups[self.nodeid.split('@')[1]].nodes[self.nodeid.split('@')[0]]
        tenode.textupdate(tenode['bt'])
        return {'FINISHED'}

class NODE_OT_TextExport(bpy.types.Operator, io_utils.ExportHelper):
    bl_idname = "node.textexport"
    bl_label = "Export a text file"
    bl_description = "Select the text file to export"
    filename = ""
    filename_ext = ".txt"
    filter_glob = bpy.props.StringProperty(default="*.txt", options={'HIDDEN'})
    bl_register = True
    bl_undo = True
    nodeid = bpy.props.StringProperty()

    def draw(self,context):
        layout = self.layout
        row = layout.row()
        row.label(text="Specify the Text export file with the file browser", icon='WORLD_DATA')

    def execute(self, context):
        hostnode = bpy.data.node_groups[self.nodeid.split('@')[1]].nodes[self.nodeid.split('@')[0]]
        textsocket = bpy.data.node_groups[self.nodeid.split('@')[1]].nodes[self.nodeid.split('@')[0]].inputs['Text in'].links[0].from_socket
        resstring = '\n'.join(textsocket['Text'])
        with open(self.filepath, 'w') as textfile:
            textfile.write(resstring)
        if hostnode.etoggle:
            if self.filepath not in [im.filepath for im in bpy.data.texts]:
                bpy.data.texts.load(self.filepath)

            imname = [im.name for im in bpy.data.texts if im.filepath == self.filepath][0]
            text = bpy.data.texts[imname]
            for area in bpy.context.screen.areas:
                if area.type == 'TEXT_EDITOR':
                    area.spaces.active.text = text
                    ctx = bpy.context.copy()
                    ctx['edit_text'] = text
                    ctx['area'] = area
                    ctx['region'] = area.regions[-1]
                    bpy.ops.text.resolve_conflict(ctx, resolution = 'RELOAD')

        return {'FINISHED'}

    def invoke(self,context,event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

class NODE_OT_EnGExport(bpy.types.Operator):
    bl_idname = "node.engexport"
    bl_label = "VI-Suite export"
    bl_context = "scene"
    nodeid = bpy.props.StringProperty()

    def invoke(self, context, event):
        scene = context.scene
        if viparams(self, scene):
            return {'CANCELLED'}
        scene['viparams']['vidisp'] = ''
        node = bpy.data.node_groups[self.nodeid.split('@')[1]].nodes[self.nodeid.split('@')[0]]
        node.preexport(scene)
        pregeo(self)
        node.postexport()
        return {'FINISHED'}

class NODE_OT_EnExport(bpy.types.Operator, io_utils.ExportHelper):
    bl_idname = "node.enexport"
    bl_label = "Export"
    bl_description = "Export the scene to the EnergyPlus file format"
    bl_register = True
    bl_undo = False
    nodeid = bpy.props.StringProperty()

    def invoke(self, context, event):
        scene = context.scene
        if viparams(self, scene):
            return {'CANCELLED'}
        scene['viparams']['vidisp'] = ''
        node = bpy.data.node_groups[self.nodeid.split('@')[1]].nodes[self.nodeid.split('@')[0]]
        (scene['enparams']['fs'], scene['enparams']['fe']) = (node.fs, node.fe) if node.animated else (scene.frame_current, scene.frame_current)
        locnode = node.inputs['Location in'].links[0].from_node
        if not os.path.isfile(locnode.weather):
            self.report({'ERROR'}, 'Location node weather file is not valid')
            node.use_custom_color = 1
            return {'CANCELLED'}
        node.preexport(scene)
        
        for frame in range(node.fs, node.fe + 1):
            scene.frame_set(frame)
            shutil.copyfile(locnode.weather, os.path.join(scene['viparams']['newdir'], "in{}.epw".format(frame)))
        scene.frame_set(node.fs)
        shutil.copyfile(os.path.join(os.path.dirname(os.path.abspath(os.path.realpath( __file__ ))), "EPFiles", "Energy+.idd"), os.path.join(scene['viparams']['newdir'], "Energy+.idd"))

        if bpy.context.active_object and not bpy.context.active_object.hide:
            if bpy.context.active_object.type == 'MESH':
                bpy.ops.object.mode_set(mode = 'OBJECT')

        enpolymatexport(self, node, locnode, envi_mats, envi_cons)
        node.bl_label = node.bl_label[1:] if node.bl_label[0] == '*' else node.bl_label
        node.exported, node.outputs['Context out'].hide = True, False
        node.postexport()
        return {'FINISHED'}

class NODE_OT_EnSim(bpy.types.Operator):
    bl_idname = "node.ensim"
    bl_label = "Simulate"
    bl_description = "Run EnergyPlus"
    bl_register = True
    bl_undo = False
    nodeid = bpy.props.StringProperty()

    def modal(self, context, event):
        if event.type == 'TIMER':
            scene = context.scene
            if self.esimrun.poll() is None:
                nodecolour(self.simnode, 1)
                try:
                    
                    with open(os.path.join(scene['viparams']['newdir'], '{}{}out.eso'.format(self.resname, self.frame)), 'r') as resfile:
                        for resline in [line for line in resfile.readlines()[::-1] if line.split(',')[0] == '2' and len(line.split(',')) == 9]:
                            if self.pfile.check(int((100/self.lenframes) * (self.frame - scene['enparams']['fs'])) + int((100/self.lenframes) * int(resline.split(',')[1])/(self.simnode.dedoy - self.simnode.dsdoy))) == 'CANCELLED':
                                self.simnode.run = -1
                                return {'CANCELLED'}
                            self.simnode.run = int((100/self.lenframes) * (self.frame - scene['enparams']['fs'])) + int((100/self.lenframes) * int(resline.split(',')[1])/(self.simnode.dedoy - self.simnode.dsdoy))
                            break
                    return {'PASS_THROUGH'}
                except Exception as e:
                    print(e)
                    return {'PASS_THROUGH'}
            elif self.frame < scene['enparams']['fe']:
                self.frame += 1
                esimcmd = "energyplus {0} -w in{1}.epw -i {2} -p {3} in{1}.idf".format(self.expand, self.frame, self.eidd, ('{}{}'.format(self.resname, self.frame))) 
                self.esimrun = Popen(esimcmd.split(), stderr = PIPE)
                return {'PASS_THROUGH'}
            else:
                self.simnode.run = -1
                for fname in [fname for fname in os.listdir('.') if fname.split(".")[0] == self.simnode.resname]:
                    os.remove(os.path.join(scene['viparams']['newdir'], fname))

                nfns = [fname for fname in os.listdir('.') if fname.split(".")[0] == "{}{}out".format(self.resname, self.frame)]
                for fname in nfns:
                    rename(os.path.join(scene['viparams']['newdir'], fname), os.path.join(scene['viparams']['newdir'],fname.replace("eplusout", self.simnode.resname)))
                
                efilename = "{}{}out.err".format(self.resname, self.frame)
                if efilename not in [im.name for im in bpy.data.texts]:
                    bpy.data.texts.load(os.path.join(scene['viparams']['newdir'], efilename))
                else:
                    bpy.data.texts[efilename].filepath = os.path.join(scene['viparams']['newdir'], efilename)
                if '** Severe  **' in bpy.data.texts[efilename]:
                    self.report({'ERROR'}, "Fatal error reported in the {} file. Check the file in Blender's text editor".format(efilename))
                    return {'CANCELLED'}

                if 'EnergyPlus Terminated--Error(s) Detected' in self.esimrun.stderr.read().decode() or not [f for f in nfns if f.split(".")[1] == "eso"] or self.simnode.run == 0:
                    errtext = "There is no results file. Check you have selected results outputs and that there are no errors in the .err file in the Blender text editor." if not [f for f in nfns if f.split(".")[1] == "eso"] else "There was an error in the input IDF file. Check the *.err file in Blender's text editor."
                    self.report({'ERROR'}, errtext)
                    self.simnode.run = -1
                    return {'CANCELLED'}
                else:
                    nodecolour(self.simnode, 0)
                    processf(self, scene, self.simnode)
                    self.report({'INFO'}, "Calculation is finished.")
                    scene['viparams']['resnode'], scene['viparams']['connode'], scene['viparams']['vidisp'] = self.nodeid, '{}@{}'.format(self.connode.name, self.nodeid.split('@')[1]), 'en'
                    self.simnode.run = -1
                    if self.kivyrun.poll() is None:
                        self.kivyrun.kill()
                    return {'FINISHED'}
        else:
            return {'PASS_THROUGH'}

    def invoke(self, context, event):
        scene = context.scene
        self.frame = scene['enparams']['fs']
        self.lenframes = len(range(scene['enparams']['fs'], scene['enparams']['fe'] + 1)) 
        if viparams(self, scene):
            return {'CANCELLED'}
        context.scene['viparams']['visimcontext'] = 'EnVi'
        self.pfile = progressfile(scene, datetime.datetime.now(), 100)
        self.kivyrun = progressbar(os.path.join(scene['viparams']['newdir'], 'viprogress'))
        wm = context.window_manager
        self._timer = wm.event_timer_add(1, context.window)
        wm.modal_handler_add(self)
        self.simnode = bpy.data.node_groups[self.nodeid.split('@')[1]].nodes[self.nodeid.split('@')[0]]
        self.simnode.presim(context)
        self.connode = self.simnode.inputs['Context in'].links[0].from_node
        self.simnode.resfilename = os.path.join(scene['viparams']['newdir'], self.simnode.resname+'.eso')
        self.expand = "-x" if scene['viparams'].get('hvactemplate') else ""
        self.eidd = os.path.join(os.path.dirname(os.path.abspath(os.path.realpath( __file__ ))), "EPFiles", "Energy+.idd")  
        self.resname = (self.simnode.resname, 'eplus')[self.simnode.resname == '']
        os.chdir(scene['viparams']['newdir'])
        esimcmd = "energyplus {0} -w in{1}.epw -i {2} -p {3} in{1}.idf".format(self.expand, self.frame, self.eidd, ('{}{}'.format(self.resname, self.frame))) 
        self.esimrun = Popen(esimcmd.split(), stderr = PIPE)
        self.simnode.run = 0
        return {'RUNNING_MODAL'}

class VIEW3D_OT_EnDisplay(bpy.types.Operator):
    bl_idname = "view3d.endisplay"
    bl_label = "EnVi display"
    bl_description = "Display the EnVi results"
    bl_options = {'REGISTER'}
#    bl_undo = True
    _handle = None
    disp =  bpy.props.IntProperty(default = 1)
    
    @classmethod
    def poll(cls, context):
        return context.area.type   == 'VIEW_3D' and \
               context.region.type == 'WINDOW'

    def modal(self, context, event):
        scene = context.scene
        if event.type != 'INBETWEEN_MOUSEMOVE' and context.region and context.area.type == 'VIEW_3D' and context.region.type == 'WINDOW':  
            if context.scene.vi_display == 0 or context.scene['viparams']['vidisp'] != 'enpanel':
                context.scene['viparams']['vidisp'] = 'en'
                bpy.types.SpaceView3D.draw_handler_remove(self._handle_en_disp, 'WINDOW')
                
                try:
                    bpy.types.SpaceView3D.draw_handler_remove(self._handle_air, 'WINDOW')
                except:
                    pass
                
                for o in [o for o in scene.objects if o.get('VIType') and o['VIType'] in ('envi_temp', 'envi_hum', 'envi_heat', 'envi_cool', 'envi_co2', 'envi_shg', 'envi_ppd', 'envi_pmv', 'envi_aheat', 'envi_acool', 'envi_hrheat')]:
                    for oc in o.children:                        
                        [scene.objects.unlink(oc) for oc in o.children]
                        bpy.data.objects.remove(oc)                    
                    scene.objects.unlink(o)
                    bpy.data.objects.remove(o)

                context.area.tag_redraw()
                return {'CANCELLED'}

            mx, my, redraw = event.mouse_region_x, event.mouse_region_y, 0
            
            if self.dhscatter.spos[0] < mx < self.dhscatter.epos[0] and self.dhscatter.spos[1] < my < self.dhscatter.epos[1]:
                if self.dhscatter.hl != (0, 1, 1, 1):  
                    self.dhscatter.hl = (0, 1, 1, 1)
                    redraw = 1  
                if event.type == 'LEFTMOUSE':
                    if event.value == 'PRESS':
                        self.dhscatter.press = 1
                        self.dhscatter.move = 0
                        return {'RUNNING_MODAL'}
                    elif event.value == 'RELEASE':
                        if not self.dhscatter.move:
                            self.dhscatter.expand = 0 if self.dhscatter.expand else 1
                        self.dhscatter.press = 0
                        self.dhscatter.move = 0
                        context.area.tag_redraw()
                        return {'RUNNING_MODAL'}
                
                elif event.type == 'ESC':
                    bpy.data.images.remove(bpy.data.images[self.dhscatter.gimage])
                    self.dhscatter.plt.close()
                    bpy.types.SpaceView3D.draw_handler_remove(self._handle_en_disp, 'WINDOW')
                    context.area.tag_redraw()
                    return {'CANCELLED'}
                    
                elif self.dhscatter.press and event.type == 'MOUSEMOVE':
                     self.dhscatter.move = 1
                     self.dhscatter.press = 0
        
            elif self.dhscatter.expand and self.dhscatter.lspos[0] < mx < self.dhscatter.lepos[0] and self.dhscatter.lspos[1] < my < self.dhscatter.lepos[1] and abs(self.dhscatter.lepos[0] - mx) > 20 and abs(self.dhscatter.lspos[1] - my) > 20: 
                self.dhscatter.hl = (1, 1, 1, 1)
                if event.type == 'LEFTMOUSE' and event.value == 'PRESS' and self.dhscatter.expand and self.dhscatter.lspos[0] < mx < self.dhscatter.lepos[0] and self.dhscatter.lspos[1] < my < self.dhscatter.lspos[1] + 0.9 * self.dhscatter.ydiff:
                    self.dhscatter.show_plot()
                    context.area.tag_redraw()
                    return {'RUNNING_MODAL'}    
                    
            elif self.dhscatter.hl != (1, 1, 1, 1):
                self.dhscatter.hl = (1, 1, 1, 1)
                redraw = 1
                
            if self.table.spos[0] < mx < self.table.epos[0] and self.table.spos[1] < my < self.table.epos[1]: 
                if self.table.hl != (0, 1, 1, 1):  
                    self.table.hl = (0, 1, 1, 1)
                    redraw = 1
                if event.type == 'LEFTMOUSE':
                    if event.value == 'PRESS':
                        self.table.press = 1
                        self.table.move = 0
                        return {'RUNNING_MODAL'}
                    elif event.value == 'RELEASE':
                        if not self.table.move:
                            self.table.expand = 0 if self.table.expand else 1
                        self.table.press = 0
                        self.table.move = 0
                        context.area.tag_redraw()
                        return {'RUNNING_MODAL'}
                
                elif event.type == 'ESC':
                    bpy.data.images.remove(self.table.gimage)
                    self.table.plt.close()
                    bpy.types.SpaceView3D.draw_handler_remove(self._handle_en_disp, 'WINDOW')
                    context.area.tag_redraw()
                    return {'CANCELLED'}
                    
                elif self.table.press and event.type == 'MOUSEMOVE':
                     self.table.move = 1
                     self.table.press = 0
            
            elif self.table.hl != (1, 1, 1, 1):
                self.table.hl = (1, 1, 1, 1)
                redraw = 1
                
            if abs(self.dhscatter.lepos[0] - mx) < 20 and abs(self.dhscatter.lspos[1] - my) < 20 and self.dhscatter.expand:
                self.dhscatter.hl = (0, 1, 1, 1) 
                if event.type == 'LEFTMOUSE':
                    if event.value == 'PRESS':
                        self.dhscatter.resize = 1
                    if self.dhscatter.resize and event.value == 'RELEASE':
                        self.dhscatter.resize = 0
                    return {'RUNNING_MODAL'}

            if abs(self.table.lepos[0] - mx) < 20 and abs(self.table.lspos[1] - my) < 20 and self.table.expand:
                self.table.hl = (0, 1, 1, 1) 
                if event.type == 'LEFTMOUSE':
                    if event.value == 'PRESS':
                        self.table.resize = 1
                    if self.table.resize and event.value == 'RELEASE':
                        self.table.resize = 0
                    return {'RUNNING_MODAL'}
    
            if event.type == 'MOUSEMOVE':                
                if self.dhscatter.move:
                    self.dhscatter.pos = [mx, my]
                    redraw = 1
                if self.dhscatter.resize:
                    self.dhscatter.lepos[0], self.dhscatter.lspos[1] = mx, my
                    redraw = 1
                if self.table.move:
                    self.table.pos = [mx, my]
                    redraw = 1
                if self.table.resize:
                    self.table.lepos[0], self.table.lspos[1] = mx, my
                    redraw = 1
    
            if self.dhscatter.unit != scene.en_disp_unit or self.dhscatter.cao != context.active_object or \
                self.dhscatter.col != scene.vi_leg_col or self.dhscatter.resstring != retenvires(scene) or \
                self.dhscatter.minmax != envals(scene.en_disp_unit, scene, [0, 100]):
                self.dhscatter.update(context)
                self.table.update(context)

            if redraw:
                context.area.tag_redraw()
                
            return {'PASS_THROUGH'}
        else:
            return {'PASS_THROUGH'}

    def execute(self, context):
        self.i = 0
        scene = context.scene
        scene.en_frame = scene.frame_current
#        (resnode, restree) = scene['viparams']['resnode'].split('@')
        resnode = bpy.data.node_groups[scene['viparams']['resnode'].split('@')[1]].nodes[scene['viparams']['resnode'].split('@')[0]]
        zrl = list(zip(*resnode['reslists']))
        eresobs = {o.name: o.name.upper() for o in bpy.data.objects if o.name.upper() in zrl[2]}
        resstart, resend = 24 * (resnode['Start'] - 1), 24 * (resnode['End']) - 1
        scene.frame_start, scene.frame_end = 0, len(zrl[4][0].split()) - 1
        
        if scene.resas_disp:
            suns = [o for o in bpy.data.objects if o.type == 'LAMP' and o.data.type == 'SUN']
            if not suns:
                bpy.ops.object.lamp_add(type='SUN')
                sun = bpy.context.object
            else:
                sun = suns[0]
            
            for mi, metric in enumerate(zrl[3]):
                if metric == 'Direct Solar (W/m^2)':
                    dirsol = [float(ds) for ds in zrl[4][mi].split()[resstart:resend]]
                elif metric == 'Diffuse Solar (W/m^2)':
                    difsol = [float(ds) for ds in zrl[4][mi].split()[resstart:resend]]
                elif metric == 'Month':
                    mdata = [int(m) for m in zrl[4][mi].split()[resstart:resend]]
                elif metric == 'Day':
                    ddata = [int(d) for d in zrl[4][mi].split()[resstart:resend]]
                elif metric == 'Hour':
                    hdata = [int(h) for h in zrl[4][mi].split()[resstart:resend]]

            sunposenvi(scene, sun, dirsol, difsol, mdata, ddata, hdata)

        if scene.resaa_disp:
            for mi, metric in enumerate(zrl[3]):
                if metric == 'Temperature (degC)' and zrl[1][mi] == 'Climate':
                    temp = [float(ds) for ds in zrl[4][mi].split()[24 * resnode['Start']:24 * resnode['End'] + 1]]
                elif metric == 'Wind Speed (m/s)' and zrl[1][mi] == 'Climate':
                    ws = [float(ds) for ds in zrl[4][mi].split()[24 * resnode['Start']:24 * resnode['End'] + 1]]
                elif metric == 'Wind Direction (deg)' and zrl[1][mi] == 'Climate':
                    wd = [float(m) for m in zrl[4][mi].split()[24 * resnode['Start']:24 * resnode['End'] + 1]]
                elif metric == 'Humidity (%)' and zrl[1][mi] == 'Climate':
                    hu = [float(d) for d in zrl[4][mi].split()[24 * resnode['Start']:24 * resnode['End'] + 1]]
            
            self._handle_air = bpy.types.SpaceView3D.draw_handler_add(en_air, (self, context, temp, ws, wd, hu), 'WINDOW', 'POST_PIXEL')        
        zmetrics = set([zr for zri, zr in enumerate(zrl[3]) if zrl[1][zri] == 'Zone'  and zrl[0][zri] != 'All'])
        
        if scene.reszt_disp and 'Temperature (degC)' in zmetrics:
            envizres(scene, eresobs, resnode, 'Temp')
        if scene.reszsg_disp and  'Solar gain (W)' in zmetrics:
            envizres(scene, eresobs, resnode, 'SHG')
        if scene.reszh_disp and 'Humidity (%)' in zmetrics:
            envizres(scene, eresobs, resnode, 'Hum')
        if scene.reszco_disp and 'CO2 (ppm)' in zmetrics:
            envizres(scene, eresobs, resnode, 'CO2')
        if scene.reszhw_disp and 'Heating (W)' in zmetrics:
            envizres(scene, eresobs, resnode, 'Heat')
        if scene.reszhw_disp and 'Cooling (W)' in zmetrics:
            envizres(scene, eresobs, resnode, 'Cool')
        if scene.reszpmv_disp and 'PMV' in zmetrics:
            envizres(scene, eresobs, resnode, 'PMV')
        if scene.reszppd_disp and 'PPD (%)' in zmetrics:
            envizres(scene, eresobs, resnode, 'PPD')
        if scene.reshrhw_disp and 'HR heating (W)' in zmetrics:
            envizres(scene, eresobs, resnode, 'HRheat')
        if scene.reszof_disp:
            envilres(scene, resnode)
        if scene.reszlf_disp:
            envilres(scene, resnode)

        scene.frame_set(scene.frame_start)
        bpy.app.handlers.frame_change_pre.clear()
        bpy.app.handlers.frame_change_pre.append(recalculate_text)
        self.dhscatter = en_scatter([160, context.region.height - 40], context.region.width, context.region.height, 'scat.png', 600, 400)
        self.dhscatter.update(context)
        self.table = en_table([240, context.region.height - 40], context.region.width, context.region.height, 'table.png', 600, 150)
        self.table.update(context)           
        self._handle_en_disp = bpy.types.SpaceView3D.draw_handler_add(en_disp, (self, context, resnode), 'WINDOW', 'POST_PIXEL')
        scene['viparams']['vidisp'] = 'enpanel'
        scene.vi_display = True
        context.window_manager.modal_handler_add(self)
#        scene.update()
        return {'RUNNING_MODAL'}

class VIEW3D_OT_EnPDisplay(bpy.types.Operator):
    bl_idname = "view3d.enpdisplay"
    bl_label = "EnVi parametric display"
    bl_description = "Display the parametric EnVi results"
    bl_options = {'REGISTER'}
#    bl_undo = False
    _handle = None
    disp =  bpy.props.IntProperty(default = 1)
    
    @classmethod
    def poll(cls, context):
        return context.area.type  == 'VIEW_3D' and \
               context.region.type == 'WINDOW'
    
    def modal(self, context, event):
        redraw = 0
        scene = context.scene

        if event.type != 'INBETWEEN_MOUSEMOVE':   
            if scene.vi_display == 0 or scene['viparams']['vidisp'] != 'enpanel':
                scene['viparams']['vidisp'] = 'en'
                bpy.types.SpaceView3D.draw_handler_remove(self._handle_en_pdisp, 'WINDOW')
                for o in [o for o in scene.objects if o.get('VIType') and o['VIType'] in ('envi_maxtemp', 'envi_maxhum', 'envi_maxheat', 'envi_maxcool', 'envi_maxco2', 'envi_maxshg', 'envi_maxppd', 'envi_maxpmv')]:
                    for oc in o.children:                        
                        [scene.objects.unlink(oc) for oc in o.children]
                        bpy.data.objects.remove(oc)                    
                    scene.objects.unlink(o)
                    bpy.data.objects.remove(o)    
                context.area.tag_redraw()
                return {'CANCELLED'}

            mx, my = event.mouse_region_x, event.mouse_region_y 
            
            if self.barchart.spos[0] < mx < self.barchart.epos[0] and self.barchart.spos[1] < my < self.barchart.epos[1]:
                if self.barchart.hl != (0, 1, 1, 1):
                    self.barchart.hl = (0, 1, 1, 1) 
                    redraw = 1
                if event.type == 'LEFTMOUSE':
                    if event.value == 'PRESS':
                        self.barchart.press = 1
                        self.barchart.move = 0
                        return {'RUNNING_MODAL'}
                    elif event.value == 'RELEASE':
                        if not self.barchart.move:
                            self.barchart.expand = 0 if self.barchart.expand else 1
                        self.barchart.press = 0
                        self.barchart.move = 0
                        context.area.tag_redraw()
                        return {'RUNNING_MODAL'}
                
                elif event.type == 'ESC':
                    bpy.data.images.remove(self.barchart.gimage)
                    self.barchart.plt.close()
                    bpy.types.SpaceView3D.draw_handler_remove(self._handle_en_disp, 'WINDOW')
                    context.area.tag_redraw()
                    return {'CANCELLED'}
                    
                elif self.barchart.press and event.type == 'MOUSEMOVE':
                     self.barchart.move = 1
                     self.barchart.press = 0
        
            elif self.barchart.lspos[0] < mx < self.barchart.lepos[0] and self.barchart.lspos[1] < my < self.barchart.lepos[1] and abs(self.barchart.lepos[0] - mx) > 20 and abs(self.barchart.lspos[1] - my) > 20:
                if self.barchart.expand: 
                    if self.barchart.hl != (0, 1, 1, 1):
                        self.barchart.hl = (0, 1, 1, 1)
                        redraw = 1
                    if event.type == 'LEFTMOUSE' and event.value == 'PRESS' and self.barchart.expand and self.barchart.lspos[0] < mx < self.barchart.lepos[0] and self.barchart.lspos[1] < my < self.barchart.lspos[1] + 0.9 * self.barchart.ydiff:
                        self.barchart.show_plot()
                        context.area.tag_redraw()
                        return {'RUNNING_MODAL'}
                        
            elif abs(self.barchart.lepos[0] - mx) < 20 and abs(self.barchart.lspos[1] - my) < 20 and self.barchart.expand:
                if self.barchart.hl != (0, 1, 1, 1):
                    self.barchart.hl = (0, 1, 1, 1) 
                    redraw = 1
                if event.type == 'LEFTMOUSE':
                    if event.value == 'PRESS':
                        self.barchart.resize = 1
                    if self.barchart.resize and event.value == 'RELEASE':
                        self.barchart.resize = 0
                    return {'RUNNING_MODAL'}
                                       
            else:
                if self.barchart.hl != (1, 1, 1, 1):
                    self.barchart.hl = (1, 1, 1, 1)
                    redraw = 1
                
            if self.table.spos[0] < mx < self.table.epos[0] and self.table.spos[1] < my < self.table.epos[1]:
                if self.table.hl != (0, 1, 1, 1):
                    self.table.hl = (0, 1, 1, 1)  
                    redraw = 1
                    
                if event.type == 'LEFTMOUSE':
                    if event.value == 'PRESS':
                        self.table.press = 1
                        self.table.move = 0
                        return {'RUNNING_MODAL'}
                    elif event.value == 'RELEASE':
                        if not self.table.move:
                            self.table.expand = 0 if self.table.expand else 1
                        self.table.press = 0
                        self.table.move = 0
                        context.area.tag_redraw()
                        return {'RUNNING_MODAL'}
                
                elif event.type == 'ESC':
                    bpy.data.images.remove(self.table.gimage)
                    self.table.plt.close()
                    bpy.types.SpaceView3D.draw_handler_remove(self._handle_en_disp, 'WINDOW')
                    context.area.tag_redraw()
                    return {'CANCELLED'}
                    
                elif self.table.press and event.type == 'MOUSEMOVE':
                     self.table.move = 1
                     self.table.press = 0

            elif abs(self.table.lepos[0] - mx) < 20 and abs(self.table.lspos[1] - my) < 20 and self.table.expand:
                if self.table.hl != (0, 1, 1, 1):
                    self.table.hl = (0, 1, 1, 1)
                    redraw = 1
                if event.type == 'LEFTMOUSE':
                    if event.value == 'PRESS':
                        self.table.resize = 1
                        return {'RUNNING_MODAL'}
                    if self.table.resize and event.value == 'RELEASE':
                        self.table.resize = 0
                        return {'RUNNING_MODAL'}
                                    
            else:
                if self.table.hl != (1, 1, 1, 1):
                    self.table.hl = (1, 1, 1, 1)
                    redraw = 1
                    
            if event.type == 'MOUSEMOVE':                
                if self.barchart.move:
                    self.barchart.pos = [mx, my]
                    redraw = 1
                           
                if self.barchart.resize:
                    self.barchart.lepos[0], self.barchart.lspos[1] = mx, my
                    redraw = 1
               
                if self.table.move:
                    self.table.pos = [mx, my]
                    redraw = 1
               
                if self.table.resize:
                    self.table.lepos[0], self.table.lspos[1] = mx, my
                    redraw = 1
            
            if self.barchart.unit != scene.en_disp_punit or self.barchart.cao != context.active_object or \
                self.barchart.resstring != retenvires(scene) or self.barchart.col != scene.vi_leg_col or self.barchart.minmax != (scene.bar_min, scene.bar_max):
                self.barchart.update(context)
                self.table.update(context)
                redraw = 1

            if redraw:
                context.area.tag_redraw()
                
            return {'PASS_THROUGH'}
        else:
            return {'PASS_THROUGH'}
                
    def execute(self, context):
        scene = context.scene
        scene.en_frame = scene.frame_current
        resnode = bpy.data.node_groups[scene['viparams']['resnode'].split('@')[1]].nodes[scene['viparams']['resnode'].split('@')[0]]
        zrl = list(zip(*resnode['reslists']))
        eresobs = {o.name: o.name.upper() for o in bpy.data.objects if o.name.upper() in zrl[2]}
        scene.frame_start, scene.frame_end = scene['enparams']['fs'], scene['enparams']['fe']                
        zmetrics = set([zr for zri, zr in enumerate(zrl[3]) if zrl[1][zri] == 'Zone' and zrl[0][zri] == 'All'])

        if scene.resazmaxt_disp and 'Max temp (C)' in zmetrics:
            envizres(scene, eresobs, resnode, 'MaxTemp')
        if scene.resazavet_disp and 'Ave temp (C)' in zmetrics:
            envizres(scene, eresobs, resnode, 'AveTemp')
        if scene.resazmint_disp and 'Min temp (C)' in zmetrics:
            envizres(scene, eresobs, resnode, 'MinTemp')
        if scene.resazmaxhw_disp and 'Max heating (W)' in zmetrics:
            envizres(scene, eresobs, resnode, 'MaxHeat')
        if scene.resazavehw_disp and 'Ave heating (W)' in zmetrics:
            envizres(scene, eresobs, resnode, 'AveHeat')
        if scene.resazminhw_disp and 'Min heating (W)' in zmetrics:
            envizres(scene, eresobs, resnode, 'MinHeat')
        if scene.reszof_disp:
            envilres(scene, resnode)
        if scene.reszlf_disp:
            envilres(scene, resnode)

        scene.frame_set(scene.frame_start)
        bpy.app.handlers.frame_change_pre.clear()
        bpy.app.handlers.frame_change_pre.append(recalculate_text)
        scene['viparams']['vidisp'] = 'enpanel'
        scene.vi_display = True
        context.window_manager.modal_handler_add(self)
        self.barchart = en_barchart([160, context.region.height - 40], context.region.width, context.region.height, 'stats.png', 600, 400)
        self.barchart.update(context)
        self.table = en_table([240, context.region.height - 40], context.region.width, context.region.height, 'table.png', 600, 150)
        self.table.update(context)
        self._handle_en_pdisp = bpy.types.SpaceView3D.draw_handler_add(en_pdisp, (self, context, resnode), 'WINDOW', 'POST_PIXEL')
        return {'RUNNING_MODAL'}

class NODE_OT_Chart(bpy.types.Operator, io_utils.ExportHelper):
    bl_idname = "node.chart"
    bl_label = "Chart"
    bl_description = "Create a 2D graph from the results file"
    bl_register = True
    bl_undo = True
    nodeid = bpy.props.StringProperty()

    def invoke(self, context, event):
        node = bpy.data.node_groups[self.nodeid.split('@')[1]].nodes[self.nodeid.split('@')[0]]
        innodes = list(OrderedDict.fromkeys([inputs.links[0].from_node for inputs in node.inputs if inputs.links]))
        rl = innodes[0]['reslists']
        zrl = list(zip(*rl))
        year = innodes[0]['year']
        
        if node.inputs['X-axis'].framemenu not in zrl[0]:
            self.report({'ERROR'},"There are no results in the results file. Check the results.err file in Blender's text editor")
            return {'CANCELLED'}
        
        if not mp:
            self.report({'ERROR'},"Matplotlib cannot be found by the Python installation used by Blender")
            return {'CANCELLED'}

        Sdate = dt.fromordinal(dt(year, 1, 1).toordinal() + node['Start'] - 1)# + datetime.timedelta(hours = node.dsh - 1)
        Edate = dt.fromordinal(dt(year, 1, 1).toordinal() + node['End'] - 1)# + datetime.timedelta(hours = node.deh - 1)
        chart_disp(self, plt, node, innodes, Sdate, Edate)
        return {'FINISHED'}

class NODE_OT_FileProcess(bpy.types.Operator, io_utils.ExportHelper):
    bl_idname = "node.fileprocess"
    bl_label = "Process"
    bl_description = "Process EnergyPlus results file"
    bl_register = True
    bl_undo = True
    nodeid = bpy.props.StringProperty()

    def invoke(self, context, event):
        node = bpy.data.node_groups[self.nodeid.split('@')[1]].nodes[self.nodeid.split('@')[0]]
        self.resname = node.filebase
        processf(self, context.scene, node)
        node.export()
        return {'FINISHED'}

class NODE_OT_SunPath(bpy.types.Operator):
    bl_idname = "node.sunpath"
    bl_label = "Sun Path"
    bl_description = "Create a Sun Path"
    bl_register = True
    bl_undo = True
    nodeid = bpy.props.StringProperty()

    def invoke(self, context, event):
        scene = context.scene
        if viparams(self, scene):
            self.report({'ERROR'},"Save the Blender file before continuing")
            return {'CANCELLED'}
        solringnum, sd, numpos = 0, 100, {}
        node = bpy.data.node_groups[self.nodeid.split('@')[1]].nodes[self.nodeid.split('@')[0]]
        node.export()
        scene['viparams']['resnode'], scene['viparams']['restree'] = node.name, self.nodeid.split('@')[1]
        scene['viparams']['vidisp'] = 'sp'
        context.scene['viparams']['visimcontext'] = 'SunPath'
        scene.cursor_location = (0.0, 0.0, 0.0)
        suns = [ob for ob in context.scene.objects if ob.type == 'LAMP' and ob.data.type == 'SUN']
        matdict = {'SolEquoRings': (1, 0, 0), 'HourRings': (1, 1, 0), 'SPBase': (1, 1, 1), 'Sun': (1, 1, 1), 'PathDash': (1, 1, 1),
                   'SumAng': (1, 0, 0), 'EquAng': (0, 1, 0), 'WinAng': (0, 0, 1)}
        
        for mat in [mat for mat in matdict if mat not in bpy.data.materials]:
            bpy.data.materials.new(mat)
            bpy.data.materials[mat].diffuse_color = matdict[mat]
            bpy.data.materials[mat].use_shadeless = 1
            if mat == 'PathDash':
                bpy.data.materials[mat].alpha = 0
                
        if suns:
            sun = suns[0]
            [scene.objects.unlink(sun) for sun in suns[1:]]
            sun.animation_data_clear()
        else: 
            bpy.ops.object.lamp_add(type = "SUN")
            sun = context.active_object
                
        sun.data.shadow_soft_size = 0.01            
        sun['VIType'] = 'Sun'
        
        if scene.render.engine == 'CYCLES' and scene.world.get('node_tree') and 'Sky Texture' in [no.bl_label for no in scene.world.node_tree.nodes]:
            scene.world.node_tree.animation_data_clear()

        sun['solhour'], sun['solday'] = scene.solhour, scene.solday

        if "SkyMesh" not in [ob.get('VIType') for ob in context.scene.objects]:
            bpy.data.materials.new('SkyMesh')
            bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, size=105)
            smesh = context.active_object
            smesh.location, smesh.rotation_euler[0], smesh.cycles_visibility.shadow, smesh.name, smesh['VIType']  = (0,0,0), pi, False, "SkyMesh", "SkyMesh"
            bpy.ops.object.material_slot_add()
            smesh.material_slots[0].material = bpy.data.materials['SkyMesh']
            bpy.ops.object.shade_smooth()
            smesh.hide = True
        else:
            smesh =  [ob for ob in context.scene.objects if ob.get('VIType') and ob['VIType'] == "SkyMesh"][0]

        if "SunMesh" not in [ob.get('VIType') for ob in context.scene.objects]:
            bpy.ops.mesh.primitive_uv_sphere_add(segments=12, ring_count=12, size=1)
            sunob = context.active_object
            sunob.location, sunob.cycles_visibility.shadow, sunob.name, sunob['VIType'] = (0, 0, 0), 0, "SunMesh", "SunMesh"
        else:
            sunob = [ob for ob in context.scene.objects if ob.get('VIType') == "SunMesh"][0]

        if len(sunob.material_slots) == 0:
             bpy.ops.object.material_slot_add()
             sunob.material_slots[0].material = bpy.data.materials['Sun']
        
        if bpy.context.active_object and not bpy.context.active_object.hide:
            if bpy.context.active_object.type == 'MESH':
                bpy.ops.object.mode_set(mode = 'OBJECT')
        
        for ob in context.scene.objects:
            if ob.get('VIType') == "SPathMesh":                
                context.scene.objects.unlink(ob)
                ob.name = 'oldspathmesh'

        bpy.ops.object.add(type = "MESH")
        spathob = context.active_object
        spathob.location, spathob.name,  spathob['VIType'], spathmesh = (0, 0, 0), "SPathMesh", "SPathMesh", spathob.data
        sun.parent = spathob
        sunob.parent = sun
        smesh.parent = spathob
        bm = bmesh.new()
        bm.from_mesh(spathmesh)

        for doy in range(0, 365, 2):
            for hour in range(1, 25):
                ([solalt, solazi]) = solarPosition(doy, hour, scene.latitude, scene.longitude)[2:]
                bm.verts.new().co = [-(sd-(sd-(sd*cos(solalt))))*sin(solazi), -(sd-(sd-(sd*cos(solalt))))*cos(solazi), sd*sin(solalt)]
        
        if hasattr(bm.verts, "ensure_lookup_table"):
            bm.verts.ensure_lookup_table()
        for v in range(24, len(bm.verts)):
            bm.edges.new((bm.verts[v], bm.verts[v - 24]))
        if v in range(8568, 8761):
            bm.edges.new((bm.verts[v], bm.verts[v - 8568]))

        for doy in (79, 172, 355):
            for hour in range(1, 241):
                ([solalt, solazi]) = solarPosition(doy, hour*0.1, scene.latitude, scene.longitude)[2:]
                vcoord = [-(sd-(sd-(sd*cos(solalt))))*sin(solazi), -(sd-(sd-(sd*cos(solalt))))*cos(solazi), sd*sin(solalt)]
                bm.verts.new().co = vcoord
                if hasattr(bm.verts, "ensure_lookup_table"):
                    bm.verts.ensure_lookup_table()
                if bm.verts[-1].co.z >= 0 and doy in (172, 355) and not hour%10:
                    numpos['{}-{}'.format(doy, int(hour*0.1))] = vcoord
                if hour != 1:
                    bm.edges.new((bm.verts[-2], bm.verts[-1]))
                    solringnum += 1
                if hour == 240:
                    bm.edges.new((bm.verts[-240], bm.verts[-1]))
                    solringnum += 1
        
        bm.to_mesh(spathmesh)
        bm.free()

        bpy.ops.object.convert(target='CURVE')
        spathob.data.bevel_depth, spathob.data.bevel_resolution = 0.15, 6
        bpy.context.object.data.fill_mode = 'FULL'
        bpy.ops.object.convert(target='MESH')
        
        bpy.ops.object.material_slot_add()
        spathob.material_slots[0].material, spathob['numpos'] = bpy.data.materials['HourRings'], numpos
        bpy.ops.object.material_slot_add()
        spathob.material_slots[1].material = bpy.data.materials['PathDash']

        for face in spathob.data.polygons:
            face.material_index = 0 if not int(face.index/16)%2 else 1
                
        for vert in spathob.data.vertices[0:16 * (solringnum + 3)]:
            vert.select = True

        bpy.ops.object.material_slot_add()
        spathob.material_slots[-1].material = bpy.data.materials['SolEquoRings']
        spathob.active_material_index = 2
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_mode(type="VERT")
        bpy.ops.object.material_slot_assign()
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.bisect(plane_co=(0.0, 0.0, 0.0), plane_no=(0.0, 0.0, 1.0), use_fill=True, clear_inner=True, clear_outer=False)
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT')
        compassos = compass((0,0,0.01), sd, spathob, bpy.data.materials['SPBase'])
        spro = spathrange([bpy.data.materials['SumAng'], bpy.data.materials['EquAng'], bpy.data.materials['WinAng']])
        objoin([compassos] + [spro] + [spathob])

        for ob in (spathob, sunob, smesh):
            ob.cycles_visibility.diffuse, ob.cycles_visibility.shadow, ob.cycles_visibility.glossy, ob.cycles_visibility.transmission, ob.cycles_visibility.scatter = [False] * 5
            ob.show_transparent = True

        if spfc not in bpy.app.handlers.frame_change_post:
            bpy.app.handlers.frame_change_post.append(spfc)

        bpy.ops.view3d.spnumdisplay('INVOKE_DEFAULT')
        return {'FINISHED'}

class VIEW3D_OT_SPNumDisplay(bpy.types.Operator):
    '''Display results legend and stats in the 3D View'''
    bl_idname = "view3d.spnumdisplay"
    bl_label = "Point numbers"
    bl_description = "Display the times and solstices on the sunpath"
    bl_register = True
    bl_undo = True

    def modal(self, context, event):
        scene = context.scene
        if context.area:
            context.area.tag_redraw()
        if scene.vi_display == 0 or scene['viparams']['vidisp'] != 'sp':
            bpy.types.SpaceView3D.draw_handler_remove(self._handle_spnum, 'WINDOW')
            [scene.objects.unlink(o) for o in scene.objects if o.get('VIType') and o['VIType'] in ('SunMesh', 'SkyMesh')]
            return {'CANCELLED'}
        return {'PASS_THROUGH'}

    def invoke(self, context, event):
        scene = context.scene
        simnode = bpy.data.node_groups[scene['viparams']['restree']].nodes[scene['viparams']['resnode']]
        self._handle_spnum = bpy.types.SpaceView3D.draw_handler_add(spnumdisplay, (self, context, simnode), 'WINDOW', 'POST_PIXEL')
        context.window_manager.modal_handler_add(self)
        scene.vi_display = 1
        return {'RUNNING_MODAL'}
        
class NODE_OT_WindRose(bpy.types.Operator):
    bl_idname = "node.windrose"
    bl_label = "Wind Rose"
    bl_description = "Create a Wind Rose"
    bl_register = True
    bl_undo = True
    nodeid = bpy.props.StringProperty()

    def invoke(self, context, event):
        scene = context.scene
        simnode = bpy.data.node_groups[self.nodeid.split('@')[1]].nodes[self.nodeid.split('@')[0]]
        if viparams(self, scene):
            return {'CANCELLED'}
        if not mp:
            self.report({'ERROR'},"There is something wrong with your matplotlib installation")
            return {'FINISHED'}

        simnode.export()
        locnode = simnode.inputs['Location in'].links[0].from_node
        scene['viparams']['resnode'], scene['viparams']['restree'] = simnode.name, self.nodeid.split('@')[1]
        scene['viparams']['vidisp'], scene.vi_display = 'wr', 1
        context.scene['viparams']['visimcontext'] = 'Wind'
        rl = locnode['reslists']
        cdoys = [float(c) for c in [r[4].split() for r in rl if r[0] == '0' and r[1] == 'Time' and r[2] == '' and r[3] == 'DOS'][0]]
        cwd = [float(c) for c in [r[4].split() for r in rl if r[0] == '0' and r[1] == 'Climate' and r[2] == '' and r[3] == 'Wind Direction (deg)'][0]]
        cws = [float(c) for c in [r[4].split() for r in rl if r[0] == '0' and r[1] == 'Climate' and r[2] == '' and r[3] == 'Wind Speed (m/s)'][0]]        
        doys = list(range(simnode.sdoy, simnode.edoy + 1)) if simnode.edoy > simnode.sdoy else list(range(1, simnode.edoy + 1)) + list(range(simnode.sdoy, 366))
        awd = array([wd for di, wd in enumerate(cwd) if cdoys[di] in doys])
        aws = array([ws for di, ws in enumerate(cws) if cdoys[di] in doys])
        validdata = numpy.where(awd > 0) if max(cwd) == 360 else numpy.where(awd > -1)
        vawd = awd[validdata]
        vaws = aws[validdata]
        simnode['maxres'], simnode['minres'], simnode['avres'] = max(cws), min(cws), sum(cws)/len(cws)
        (fig, ax) = wr_axes()
        sbinvals = arange(0,int(ceil(max(cws))),2)
        dbinvals = arange(-11.25,372.25,22.5)
        dfreq = histogram(awd, bins=dbinvals)[0]
        adfreq = histogram(cwd, bins=dbinvals)[0]
        dfreq[0] = dfreq[0] + dfreq[-1]
        dfreq = dfreq[:-1]
        
        if simnode.wrtype == '0':
            ax.bar(vawd, vaws, bins=sbinvals, normed=True, opening=0.8, edgecolor='white', cmap=cm.get_cmap(scene.vi_leg_col))
        elif simnode.wrtype == '1':
            ax.box(vawd, vaws, bins=sbinvals, normed=True, cmap=cm.get_cmap(scene.vi_leg_col))
        elif simnode.wrtype in ('2', '3', '4'):
            ax.contourf(vawd, vaws, bins=sbinvals, normed=True, cmap=cm.get_cmap(scene.vi_leg_col))

        plt.savefig(scene['viparams']['newdir']+'/disp_wind.svg')
        (wro, scale) = wind_rose(simnode['maxres'], scene['viparams']['newdir']+'/disp_wind.svg', simnode.wrtype)
        wro['maxres'], wro['minres'], wro['avres'], wro['nbins'], wro['VIType'] = max(aws), min(aws), sum(aws)/len(aws), len(sbinvals), 'Wind_Plane'
        simnode['maxfreq'] = 100*numpy.max(adfreq)/len(cwd)
        windnum(simnode['maxfreq'], (0,0,0), scale, compass((0,0,0), scale, wro, wro.data.materials['wr-000000']))
        
        plt.close()
        wro['table'] = array([["", 'Minimum', 'Average', 'Maximum'], ['Speed (m/s)', wro['minres'], '{:.1f}'.format(wro['avres']), wro['maxres']], ['Direction (\u00B0)', min(awd), '{:.1f}'.format(sum(awd)/len(awd)), max(awd)]])
        wro['ws'] = aws.reshape(len(doys), 24).T
        wro['wd'] = awd.reshape(len(doys), 24).T
        wro['days'] = array(doys, dtype = float)
        wro['hours'] = arange(1, 25, dtype = float)
        wro['maxfreq'] = 100*numpy.max(dfreq)/len(awd)
        
        simnode['nbins'] = len(sbinvals)
        simnode['ws'] = array(cws).reshape(365, 24).T
        simnode['wd'] = array(cwd).reshape(365, 24).T
        simnode['days'] = arange(1, 366, dtype = float)
        simnode['hours'] = arange(1, 25, dtype = float)
        return {'FINISHED'}

class VIEW3D_OT_WRDisplay(bpy.types.Operator):
    '''Display results legend and stats in the 3D View'''
    bl_idname = "view3d.wrdisplay"
    bl_label = "Wind rose display"
    bl_description = "Display wind metrics"
    bl_register = True
    bl_undo = False

    def modal(self, context, event): 
        if context.scene.vi_display == 0 or context.scene['viparams']['vidisp'] != 'wrpanel' or 'Wind_Plane' not in [o['VIType'] for o in bpy.data.objects if o.get('VIType')]:
                bpy.types.SpaceView3D.draw_handler_remove(self._handle_wr_disp, 'WINDOW')
                context.area.tag_redraw()
                return {'CANCELLED'}           

        if event.type != 'INBETWEEN_MOUSEMOVE' and context.region and context.area.type == 'VIEW_3D' and context.region.type == 'WINDOW':            
            mx, my = event.mouse_region_x, event.mouse_region_y 
            
            # Legend routine 
            
            if self.legend.spos[0] < mx < self.legend.epos[0] and self.legend.spos[1] < my < self.legend.epos[1]:
                self.legend.hl = (0, 1, 1, 1)  
                if event.type == 'LEFTMOUSE':
                    if event.value == 'PRESS':
                        self.legend.press = 1
                        self.legend.move = 0
                        return {'RUNNING_MODAL'}
                    elif event.value == 'RELEASE':
                        if not self.legend.move:
                            self.legend.expand = 0 if self.legend.expand else 1
                        self.legend.press = 0
                        self.legend.move = 0
                        context.area.tag_redraw()
                        return {'RUNNING_MODAL'}
                
                elif event.type == 'ESC':
                    bpy.types.SpaceView3D.draw_handler_remove(self._handle_wr_disp, 'WINDOW')
                    context.area.tag_redraw()
                    return {'CANCELLED'}
                    
                elif self.legend.press and event.type == 'MOUSEMOVE':
                     self.legend.move = 1
                     self.legend.press = 0
            
            elif abs(self.legend.lepos[0] - mx) < 10 and abs(self.legend.lspos[1] - my) < 10:
                self.legend.hl = (0, 1, 1, 1) 
                if event.type == 'LEFTMOUSE':
                    if event.value == 'PRESS':
                        self.legend.resize = 1
                    if self.legend.resize and event.value == 'RELEASE':
                        self.legend.resize = 0
                    return {'RUNNING_MODAL'}
                    
            else:
                self.legend.hl = (1, 1, 1, 1)
                
            # Scatter routine
                
            if self.dhscatter.spos[0] < mx < self.dhscatter.epos[0] and self.dhscatter.spos[1] < my < self.dhscatter.epos[1]:
                self.dhscatter.hl = (0, 1, 1, 1)  
                if event.type == 'LEFTMOUSE':
                    if event.value == 'PRESS':
                        self.dhscatter.press = 1
                        self.dhscatter.move = 0
                        return {'RUNNING_MODAL'}
                    elif event.value == 'RELEASE':
                        if not self.dhscatter.move:
                            self.dhscatter.expand = 0 if self.dhscatter.expand else 1
                        self.dhscatter.press = 0
                        self.dhscatter.move = 0
                        context.area.tag_redraw()
                        return {'RUNNING_MODAL'}
                
                elif event.type == 'ESC':
                    bpy.data.images.remove(self.dhscatter.gimage)
                    self.dhscatter.plt.close()
                    bpy.types.SpaceView3D.draw_handler_remove(self._handle_wr_disp, 'WINDOW')
                    context.area.tag_redraw()
                    return {'CANCELLED'}
                    
                elif self.dhscatter.press and event.type == 'MOUSEMOVE':
                     self.dhscatter.move = 1
                     self.dhscatter.press = 0
        
            elif self.dhscatter.lspos[0] < mx < self.dhscatter.lepos[0] and self.dhscatter.lspos[1] < my < self.dhscatter.lepos[1] and abs(self.dhscatter.lepos[0] - mx) > 20 and abs(self.dhscatter.lspos[1] - my) > 20:
                if self.dhscatter.expand: 
                    self.dhscatter.hl = (1, 1, 1, 1)
                    if event.type == 'LEFTMOUSE' and event.value == 'PRESS' and self.dhscatter.expand and self.dhscatter.lspos[0] < mx < self.dhscatter.lepos[0] and self.dhscatter.lspos[1] < my < self.dhscatter.lspos[1] + 0.9 * self.dhscatter.ydiff:
                        self.dhscatter.show_plot()
                    context.area.tag_redraw()
                    return {'RUNNING_MODAL'}
                   
            else:
                self.dhscatter.hl = (1, 1, 1, 1)
                                    
            # Table routine
                     
            if self.table.spos[0] < mx < self.table.epos[0] and self.table.spos[1] < my < self.table.epos[1]:
                self.table.hl = (0, 1, 1, 1)  
                if event.type == 'LEFTMOUSE':
                    if event.value == 'PRESS':
                        self.table.press = 1
                        self.table.move = 0
                        return {'RUNNING_MODAL'}
                    elif event.value == 'RELEASE':
                        if not self.table.move:
                            self.table.expand = 0 if self.table.expand else 1
                        self.table.press = 0
                        self.table.move = 0
                        context.area.tag_redraw()
                        return {'RUNNING_MODAL'}
                
                elif event.type == 'ESC':
                    bpy.types.SpaceView3D.draw_handler_remove(self._handle_wr_disp, 'WINDOW')
                    context.area.tag_redraw()
                    return {'CANCELLED'}
                    
                elif self.table.press and event.type == 'MOUSEMOVE':
                     self.table.move = 1
                     self.table.press = 0
                     
            else:
                self.table.hl = (1, 1, 1, 1)
                     
            # Resize routines
            
            if abs(self.legend.lepos[0] - mx) < 20 and abs(self.legend.lspos[1] - my) < 20:
                self.legend.hl = (0, 1, 1, 1) 
                if event.type == 'LEFTMOUSE':
                    if event.value == 'PRESS':
                        self.legend.resize = 1
                    if self.legend.resize and event.value == 'RELEASE':
                        self.legend.resize = 0
                    return {'RUNNING_MODAL'}
                    
            elif abs(self.dhscatter.lepos[0] - mx) < 20 and abs(self.dhscatter.lspos[1] - my) < 20:
                self.dhscatter.hl = (0, 1, 1, 1) 
                if event.type == 'LEFTMOUSE':
                    if event.value == 'PRESS':
                        self.dhscatter.resize = 1
                    if self.dhscatter.resize and event.value == 'RELEASE':
                        self.dhscatter.resize = 0
                    return {'RUNNING_MODAL'}
                    
            elif abs(self.table.lepos[0] - mx) < 20 and abs(self.table.lspos[1] - my) < 20:
                self.table.hl = (0, 1, 1, 1) 
                if event.type == 'LEFTMOUSE':
                    if event.value == 'PRESS':
                        self.table.resize = 1
                    if self.table.resize and event.value == 'RELEASE':
                        self.table.resize = 0
                    return {'RUNNING_MODAL'}
            
            # Move routines
                     
            if event.type == 'MOUSEMOVE':                
                if self.legend.move:
                    self.legend.pos = [mx, my]
                if self.legend.resize:
                    self.legend.lepos[0], self.legend.lspos[1] = mx, my
                if self.dhscatter.move:
                    self.dhscatter.pos = [mx, my]
                if self.dhscatter.resize:
                    self.dhscatter.lepos[0], self.dhscatter.lspos[1] = mx, my
                if self.table.move:
                    self.table.pos = [mx, my]
                if self.table.resize:
                    self.table.lepos[0], self.table.lspos[1] = mx, my
                                                
        # Object update routines 
        
            if self.legend.cao != context.active_object:
                self.legend.update(context)
            
            if self.dhscatter.cao != context.active_object or self.dhscatter.unit != context.scene.wind_type or context.scene.vi_leg_col != self.dhscatter.col:
                self.dhscatter.update(context)
                
            if self.table.cao != context.active_object:
                self.table.update(context)
            
            context.area.tag_redraw()
        return {'PASS_THROUGH'}

    def invoke(self, context, event):
        context.scene.vi_display = 1
        context.scene['viparams']['vidisp'] = 'wrpanel'
        simnode = bpy.data.node_groups[context.scene['viparams']['restree']].nodes[context.scene['viparams']['resnode']]
        self.legend = wr_legend([80, context.region.height - 40], context.region.width, context.region.height, 'legend.png', 150, 350)
        self.dhscatter = wr_scatter([160, context.region.height - 40], context.region.width, context.region.height, 'scat.png', 600, 400)
        self.table = wr_table([240, context.region.height - 40], context.region.width, context.region.height, 'table.png', 600, 150)       
        self.legend.update(context)
        self.dhscatter.update(context)
        self.table.update(context)
        self._handle_wr_disp = bpy.types.SpaceView3D.draw_handler_add(wr_disp, (self, context, simnode), 'WINDOW', 'POST_PIXEL')
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

class NODE_OT_Shadow(bpy.types.Operator):
    bl_idname = "node.shad"
    bl_label = "Shadow Study"
    bl_description = "Undertake a shadow study"
    bl_register = True
    bl_undo = False
    nodeid = bpy.props.StringProperty()

    def invoke(self, context, event):
        scene = context.scene        
        if viparams(self, scene):            
            return {'CANCELLED'}

        shadobs = retobjs('livig')
        if not shadobs:
            self.report({'ERROR'},"No shading objects have a material attached.")
            return {'CANCELLED'}
            
        scene['liparams']['shadc'] = [ob.name for ob in retobjs('ssc')]
        if not scene['liparams']['shadc']:
            self.report({'ERROR'},"No objects have a VI Shadow material attached.")
            return {'CANCELLED'}

        scene['viparams']['restree'] = self.nodeid.split('@')[1]
        scene['viparams']['vidisp'] = 'ss'
        clearscene(scene, self)
        simnode = bpy.data.node_groups[self.nodeid.split('@')[1]].nodes[self.nodeid.split('@')[0]]
        scene['viparams']['visimcontext'] = 'Shadow'
        if not scene.get('liparams'):
           scene['liparams'] = {}
        scene['liparams']['cp'], scene['liparams']['unit'], scene['liparams']['type'] = simnode.cpoint, '% Sunlit', 'VI Shadow'
        simnode.preexport()
        (scene['liparams']['fs'], scene['liparams']['fe']) = (scene.frame_current, scene.frame_current) if simnode.animmenu == 'Static' else (simnode.startframe, simnode.endframe)
        cmap('grey')

        if simnode.starthour > simnode.endhour:
            self.report({'ERROR'},"End hour is before start hour.")
            return{'CANCELLED'}
        
        scene['viparams']['resnode'], simnode['Animation'] = simnode.name, simnode.animmenu
        (scmaxres, scminres, scavres) = [[x] * (scene['liparams']['fe'] - scene['liparams']['fs'] + 1) for x in (0, 100, 0)]
        
        frange = range(scene['liparams']['fs'], scene['liparams']['fe'] + 1)
        time = datetime.datetime(2014, simnode.sdate.month, simnode.sdate.day, simnode.starthour - 1)
        y =  2014 if simnode.edoy >= simnode.sdoy else 2014 + 1
        endtime = datetime.datetime(y, simnode.edate.month, simnode.edate.day, simnode.endhour - 1)
        interval = datetime.timedelta(hours = 1/simnode.interval)
        
        times = [time + interval*t for t in range(int((endtime - time)/interval) + simnode.interval) if simnode.starthour - 1 <= (time + interval*t).hour <= simnode.endhour  - 1]
        sps = [solarPosition(t.timetuple().tm_yday, t.hour+t.minute/60, scene.latitude, scene.longitude)[2:] for t in times]
        direcs = [mathutils.Vector((-sin(sp[1]), -cos(sp[1]), tan(sp[0]))) for sp in sps]# if sp[0] > 0]   
        valdirecs = [mathutils.Vector((-sin(sp[1]), -cos(sp[1]), tan(sp[0]))) for sp in sps if sp[0] > 0]  
        lvaldirecs = len(valdirecs)
        calcsteps = len(frange) * sum(len([f for f in o.data.polygons if o.data.materials[f.material_index].mattype == '1']) for o in [scene.objects[on] for on in scene['liparams']['shadc']])
        curres, reslists = 0, []
        pfile = progressfile(scene, datetime.datetime.now(), calcsteps)
        kivyrun = progressbar(os.path.join(scene['viparams']['newdir'], 'viprogress'))
        
        for oi, o in enumerate([scene.objects[on] for on in scene['liparams']['shadc']]):
            for k in o.keys():
                del o[k]
            o['omin'], o['omax'], o['oave'] = {}, {}, {}
            o['days'] = arange(simnode.sdoy, simnode.edoy + 1, dtype = float)
            o['hours'] = arange(simnode.starthour, simnode.endhour + 1, 1/simnode.interval, dtype = float)
            bm = bmesh.new()
            bm.from_mesh(o.data)
            clearlayers(bm, 'a')
            bm.transform(o.matrix_world)
            geom = bm.faces if simnode.cpoint == '0' else bm.verts
            geom.layers.int.new('cindex')
            cindex = geom.layers.int['cindex']
            [geom.layers.float.new('res{}'.format(fi)) for fi in frange]
            avres, minres, maxres, g = [], [], [], 0
            if simnode.cpoint == '0':
                gpoints = [f for f in geom if o.data.materials[f.material_index].mattype == '1']
            elif simnode.cpoint == '1':
                gpoints = [v for v in geom if any([o.data.materials[f.material_index].mattype == '1' for f in v.link_faces])]

            for g, gp in enumerate(gpoints):
                gp[cindex] = g + 1

            for frame in frange: 
                g = 0                
                scene.frame_set(frame)
                shadtree = rettree(scene, shadobs, ('', '2')[simnode.signore])
                shadres = geom.layers.float['res{}'.format(frame)]
                                    
                if gpoints:
                    posis = [gp.calc_center_bounds() + gp.normal.normalized() * simnode.offset for gp in gpoints] if simnode.cpoint == '0' else [gp.co + gp.normal.normalized() * simnode.offset for gp in gpoints]
                    allpoints = numpy.zeros((len(gpoints), len(direcs)), dtype=int8)

                    for chunk in chunks(gpoints, int(scene['viparams']['nproc']) * 200):
                        for gp in chunk:
#                           Attempy to multi-process but Pool does does not with class instances
#                            p = Pool(4) 
#                            pointres = array(p.starmap(shadtree.ray_cast, [(posis[g], direc) for direc in direcs]), dtype = int8)
                            pointres = array([(0, 1)[shadtree.ray_cast(posis[g], direc)[3] == None and direc[2] > 0] for direc in direcs], dtype = int8)
                            numpy.putmask(allpoints[g], pointres == 1, pointres)
                            gp[shadres] = 100 * (numpy.sum(pointres)/lvaldirecs)
                            g += 1

                        curres += len(chunk)
                        if pfile.check(curres) == 'CANCELLED':
                            return {'CANCELLED'}
    
                    ap = numpy.average(allpoints, axis=0)                
                    shadres = [gp[shadres] for gp in gpoints]

                    o['dhres{}'.format(frame)] = array(100 * ap).reshape(len(o['days']), len(o['hours'])).T
                    o['omin']['res{}'.format(frame)], o['omax']['res{}'.format(frame)], o['oave']['res{}'.format(frame)] = min(shadres), max(shadres), sum(shadres)/len(shadres)
                    reslists.append([str(frame), 'Zone', o.name, 'X', ' '.join(['{:.3f}'.format(p[0]) for p in posis])])
                    reslists.append([str(frame), 'Zone', o.name, 'Y', ' '.join(['{:.3f}'.format(p[1]) for p in posis])])
                    reslists.append([str(frame), 'Zone', o.name, 'Z', ' '.join(['{:.3f}'.format(p[2]) for p in posis])])
                    reslists.append([str(frame), 'Zone', o.name, 'Sunlit %', ' '.join(['{:.3f}'.format(sr) for sr in shadres])])
                    avres.append(o['oave']['res{}'.format(frame)])
                    minres.append(o['omin']['res{}'.format(frame)])
                    maxres.append(o['omax']['res{}'.format(frame)])

            reslists.append(['All', 'Frames', '', 'Frames', ' '.join(['{}'.format(f) for f in frange])])
            reslists.append(['All', 'Zone', o.name, 'Minimum', ' '.join(['{:.3f}'.format(mr) for mr in minres])])
            reslists.append(['All', 'Zone', o.name, 'Average', ' '.join(['{:.3f}'.format(mr) for mr in avres])])
            reslists.append(['All', 'Zone', o.name, 'Maximum', ' '.join(['{:.3f}'.format(mr) for mr in maxres])])
            bm.transform(o.matrix_world.inverted())
            bm.to_mesh(o.data)
            bm.free()

        scene.vi_leg_max, scene.vi_leg_min = 100, 0

        if kivyrun.poll() is None:
            kivyrun.kill()
        
        scene.frame_start, scene.frame_end = scene['liparams']['fs'], scene['liparams']['fe']
        scene.vi_display = 1
        simnode['reslists'] = reslists
        simnode['frames'] = [f for f in frange]
        simnode['year'] = 2015
        simnode.postexport(scene)
        return {'FINISHED'}
        
class VIEW3D_OT_SSDisplay(bpy.types.Operator):
    '''Display results legend and stats in the 3D View'''
    bl_idname = "view3d.ssdisplay"
    bl_label = "Shadow study metric display"
    bl_description = "Display shadow study metrics"
    bl_register = True
    bl_undo = False

    def modal(self, context, event):  
        redraw = 0         
        if event.type != 'INBETWEEN_MOUSEMOVE' and context.region and context.area.type == 'VIEW_3D' and context.region.type == 'WINDOW':            
            if context.scene.vi_display == 0 or context.scene['viparams']['vidisp'] != 'sspanel' or not [o.lires for o in bpy.data.objects]:
                bpy.types.SpaceView3D.draw_handler_remove(self._handle_ss_disp, 'WINDOW')
                bpy.types.SpaceView3D.draw_handler_remove(self._handle_pointres, 'WINDOW')
                context.area.tag_redraw()
                context.scene['viparams']['vidisp'] = 'ss'
                return {'CANCELLED'}
            
            mx, my = event.mouse_region_x, event.mouse_region_y 
            
            if any((context.scene.vi_leg_col != self.legend.col, context.scene.vi_leg_scale != self.legend.scale, self.legend.maxres != context.scene.vi_leg_max, self.legend.minres != context.scene.vi_leg_min)):               
                self.legend.update(context)
            
            # Legend routine 
            
            if self.legend.spos[0] < mx < self.legend.epos[0] and self.legend.spos[1] < my < self.legend.epos[1]:
                if self.legend.hl != (0, 1, 1, 1):  
                    self.legend.hl = (0, 1, 1, 1) 
                    redraw = 1
                if event.type == 'LEFTMOUSE':
                    if event.value == 'PRESS':
                        self.legend.press = 1
                        self.legend.move = 0
                        return {'RUNNING_MODAL'}
                    elif event.value == 'RELEASE':
                        if not self.legend.move:
                            self.legend.expand = 0 if self.legend.expand else 1
                        self.legend.press = 0
                        self.legend.move = 0
                        context.area.tag_redraw()
                        return {'RUNNING_MODAL'}
                
                elif event.type == 'ESC':
                    bpy.types.SpaceView3D.draw_handler_remove(self._handle_ss_disp, 'WINDOW')
                    context.area.tag_redraw()
                    return {'CANCELLED'}
                    
                elif self.legend.press and event.type == 'MOUSEMOVE':
                     self.legend.move = 1
                     self.legend.press = 0
            
            elif abs(self.legend.lepos[0] - mx) < 10 and abs(self.legend.lspos[1] - my) < 10:
                self.legend.hl = (0, 1, 1, 1) 
                if event.type == 'LEFTMOUSE':
                    if event.value == 'PRESS':
                        self.legend.resize = 1
                    if self.legend.resize and event.value == 'RELEASE':
                        self.legend.resize = 0
                    return {'RUNNING_MODAL'}
                    
            else:
                if self.legend.hl != (1, 1, 1, 1):
                    self.legend.hl = (1, 1, 1, 1)
                    redraw = 1
            
            # Scatter routine
                
            if self.dhscatter.spos[0] < mx < self.dhscatter.epos[0] and self.dhscatter.spos[1] < my < self.dhscatter.epos[1]:
                if self.dhscatter.hl != (0, 1, 1, 1):  
                    self.dhscatter.hl = (0, 1, 1, 1)
                    redraw = 1
                if event.type == 'LEFTMOUSE':
                    if event.value == 'PRESS':
                        self.dhscatter.press = 1
                        self.dhscatter.move = 0
                        return {'RUNNING_MODAL'}
                    elif event.value == 'RELEASE':
                        if not self.dhscatter.move:
                            self.dhscatter.expand = 0 if self.dhscatter.expand else 1
                        self.dhscatter.press = 0
                        self.dhscatter.move = 0
                        context.area.tag_redraw()
                        return {'RUNNING_MODAL'}
                
                elif event.type == 'ESC':
                    bpy.data.images.remove(self.dhscatter.gimage)
                    self.dhscatter.plt.close()
                    bpy.types.SpaceView3D.draw_handler_remove(self._handle_wr_disp, 'WINDOW')
                    context.area.tag_redraw()
                    return {'CANCELLED'}
                    
                elif self.dhscatter.press and event.type == 'MOUSEMOVE':
                     self.dhscatter.move = 1
                     self.dhscatter.press = 0
        
            elif self.dhscatter.lspos[0] < mx < self.dhscatter.lepos[0] and self.dhscatter.lspos[1] < my < self.dhscatter.lepos[1] and abs(self.dhscatter.lepos[0] - mx) > 20 and abs(self.dhscatter.lspos[1] - my) > 20:
                if self.dhscatter.expand: 
                    self.dhscatter.hl = (0, 1, 1, 1)
                    if event.type == 'LEFTMOUSE' and event.value == 'PRESS' and self.dhscatter.expand and self.dhscatter.lspos[0] < mx < self.dhscatter.lepos[0] and self.dhscatter.lspos[1] < my < self.dhscatter.lspos[1] + 0.9 * self.dhscatter.ydiff:
                        self.dhscatter.show_plot()

                    context.area.tag_redraw()
                    return {'RUNNING_MODAL'}
                   
            else:
                if self.dhscatter.hl != (1, 1, 1, 1):
                    self.dhscatter.hl = (1, 1, 1, 1)
                    redraw = 1

            # Update routine
                
            if self.dhscatter.frame != context.scene.frame_current or self.dhscatter.cao != context.active_object or self.dhscatter.col != context.scene.vi_leg_col:
                self.dhscatter.update(context)
                redraw = 1
                         
            # Resize routines
            
            if abs(self.legend.lepos[0] - mx) < 20 and abs(self.legend.lspos[1] - my) < 20:
                self.legend.hl = (0, 1, 1, 1) 
                if event.type == 'LEFTMOUSE':
                    if event.value == 'PRESS':
                        self.legend.resize = 1
                    if self.legend.resize and event.value == 'RELEASE':
                        self.legend.resize = 0
                    return {'RUNNING_MODAL'}
            
            if abs(self.dhscatter.lepos[0] - mx) < 20 and abs(self.dhscatter.lspos[1] - my) < 20:
                self.dhscatter.hl = (0, 1, 1, 1) 
                if event.type == 'LEFTMOUSE':
                    if event.value == 'PRESS':
                        self.dhscatter.resize = 1
                    if self.dhscatter.resize and event.value == 'RELEASE':
                        self.dhscatter.resize = 0
                    return {'RUNNING_MODAL'}
            
            # Move routines
                     
            if event.type == 'MOUSEMOVE':                
                if self.legend.move:
                    self.legend.pos = [mx, my]
                    redraw = 1
                if self.legend.resize:
                    self.legend.lepos[0], self.legend.lspos[1] = mx, my
                    redraw = 1
                if self.dhscatter.move:
                    self.dhscatter.pos = [mx, my]
                    redraw = 1
                if self.dhscatter.resize:
                    self.dhscatter.lepos[0], self.dhscatter.lspos[1] = mx, my
                    redraw = 1
            
            if redraw:
                context.area.tag_redraw()

        return {'PASS_THROUGH'}

    def invoke(self, context, event):
        scene = context.scene
        try:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle_pointres, 'WINDOW')
            bpy.types.SpaceView3D.draw_handler_remove(self._handle_ss_disp, 'WINDOW')
        except:
            pass
        clearscene(scene, self)
        scene.vi_display = 1
        scene['viparams']['vidisp'] = 'sspanel'
        self.simnode = bpy.data.node_groups[context.scene['viparams']['restree']].nodes[context.scene['viparams']['resnode']]
        li_display(self, self.simnode)
        scene.vi_disp_wire, scene.vi_display = 1, 1
        lnd = linumdisplay(self, context, self.simnode)
        self._handle_pointres = bpy.types.SpaceView3D.draw_handler_add(lnd.draw, (context, ), 'WINDOW', 'POST_PIXEL')
        self.legend = ss_legend([80, context.region.height - 40], context.region.width, context.region.height, 'legend.png', 150, 600)
        self.dhscatter = ss_scatter([160, context.region.height - 40], context.region.width, context.region.height, 'scat.png', 600, 400)
        self.legend.update(context)
        self.dhscatter.update(context)
        self._handle_ss_disp = bpy.types.SpaceView3D.draw_handler_add(ss_disp, (self, context, self.simnode), 'WINDOW', 'POST_PIXEL')
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}
        
class VIEW3D_OT_LiViBasicDisplay(bpy.types.Operator):
    '''Display results legend and stats in the 3D View'''
    bl_idname = "view3d.livibasicdisplay"
    bl_label = "LiVi basic metric display"
    bl_description = "Display basic lighting metrics"
    bl_register = True
    bl_undo = False

    def modal(self, context, event):   
        redraw = 0 
        if context.scene.vi_display == 0 or context.scene['viparams']['vidisp'] != 'lipanel' or not any([o.lires for o in bpy.data.objects]):
            context.scene.vi_display = 0
            bpy.types.SpaceView3D.draw_handler_remove(self._handle_disp, 'WINDOW')
            bpy.types.SpaceView3D.draw_handler_remove(self._handle_pointres, 'WINDOW')
            context.scene['viparams']['vidisp'] = 'li'
            context.area.tag_redraw()
            return {'CANCELLED'}

        if context.region and context.area.type == 'VIEW_3D' and context.region.type == 'WINDOW':            
            mx, my = event.mouse_region_x, event.mouse_region_y 
            
            if any((context.scene.vi_leg_col != self.legend.col, context.scene.vi_leg_scale != self.legend.scale, self.legend.maxres != context.scene.vi_leg_max, self.legend.minres != context.scene.vi_leg_min)):               
                self.legend.update(context)
            
            # Legend routine 
            
            if self.legend.spos[0] < mx < self.legend.epos[0] and self.legend.spos[1] < my < self.legend.epos[1]:
                if self.legend.hl != (0, 1, 1, 1):
                    self.legend.hl = (0, 1, 1, 1)
                    redraw = 1  
                if event.type == 'LEFTMOUSE':
                    if event.value == 'PRESS':
                        self.legend.press = 1
                        self.legend.move = 0
                        return {'RUNNING_MODAL'}
                    elif event.value == 'RELEASE':
                        if not self.legend.move:
                            self.legend.expand = 0 if self.legend.expand else 1
                        self.legend.press = 0
                        self.legend.move = 0
                        context.area.tag_redraw()
                        return {'RUNNING_MODAL'}
                
                elif event.type == 'ESC':
                    bpy.types.SpaceView3D.draw_handler_remove(self._handle_disp, 'WINDOW')
                    bpy.types.SpaceView3D.draw_handler_remove(self._handle_pointres, 'WINDOW')
                    context.scene['viparams']['vidisp'] = 'li'
                    context.area.tag_redraw()
                    return {'CANCELLED'}
                    
                elif self.legend.press and event.type == 'MOUSEMOVE':
                     self.legend.move = 1
                     self.legend.press = 0
            
            elif abs(self.legend.lepos[0] - mx) < 10 and abs(self.legend.lspos[1] - my) < 10:
                if self.legend.hl != (0, 1, 1, 1):
                    self.legend.hl = (0, 1, 1, 1)
                    redraw = 1
                if event.type == 'LEFTMOUSE':
                    if event.value == 'PRESS':
                        self.legend.resize = 1
                    if self.legend.resize and event.value == 'RELEASE':
                        self.legend.resize = 0
                    return {'RUNNING_MODAL'}
                    
            elif self.legend.hl != (1, 1, 1, 1):
                self.legend.hl = (1, 1, 1, 1)
                redraw = 1

            # Table routine
            
            if self.frame != context.scene.frame_current or self.table.unit != context.scene['liparams']['unit'] or self.table.cao != context.active_object:
                self.table.update(context)                
                redraw = 1
            
            if self.table.spos[0] < mx < self.table.epos[0] and self.table.spos[1] < my < self.table.epos[1]:
                if self.table.hl != (0, 1, 1, 1):
                    self.table.hl = (0, 1, 1, 1)
                    redraw = 1  
                if event.type == 'LEFTMOUSE':
                    if event.value == 'PRESS':
                        self.table.press = 1
                        self.table.move = 0
                        return {'RUNNING_MODAL'}
                    elif event.value == 'RELEASE':
                        if not self.table.move:
                            self.table.expand = 0 if self.table.expand else 1
                        self.table.press = 0
                        self.table.move = 0
                        context.area.tag_redraw()
                        return {'RUNNING_MODAL'}
                
                elif event.type == 'ESC':
                    bpy.types.SpaceView3D.draw_handler_remove(self._handle_disp, 'WINDOW')
                    bpy.types.SpaceView3D.draw_handler_remove(self._handle_pointres, 'WINDOW')
                    context.scene['viparams']['vidisp'] = 'li'
                    context.area.tag_redraw()
                    return {'CANCELLED'}
                    
                elif self.table.press and event.type == 'MOUSEMOVE':
                     self.table.move = 1
                     self.table.press = 0                     
            elif self.table.hl != (1, 1, 1, 1):
                self.table.hl = (1, 1, 1, 1)
                redraw = 1
                
            if context.scene['viparams']['visimcontext'] == 'LiVi Compliance':
                if self.frame != context.scene.frame_current:
                    self.tablecomp.update(context)
                    redraw = 1
                if self.tablecomp.unit != context.scene['liparams']['unit']:
                    self.tablecomp.update(context)
                    self.tablecomp.unit = context.scene['liparams']['unit']
                    redraw = 1
                if self.tablecomp.cao != context.active_object:
                    self.tablecomp.update(context)
                    redraw = 1
                
                if self.tablecomp.spos[0] < mx < self.tablecomp.epos[0] and self.tablecomp.spos[1] < my < self.tablecomp.epos[1]:
                    if self.tablecomp.hl != (0, 1, 1, 1):
                        self.tablecomp.hl = (0, 1, 1, 1)
                        redraw = 1  
                    if event.type == 'LEFTMOUSE':
                        if event.value == 'PRESS':
                            self.tablecomp.press = 1
                            self.tablecomp.move = 0
                            return {'RUNNING_MODAL'}
                        elif event.value == 'RELEASE':
                            if not self.tablecomp.move:
                                self.tablecomp.expand = 0 if self.tablecomp.expand else 1
                            self.tablecomp.press = 0
                            self.tablecomp.move = 0
                            context.area.tag_redraw()
                            return {'RUNNING_MODAL'}
                    
                    elif event.type == 'ESC':
                        bpy.types.SpaceView3D.draw_handler_remove(self._handle_disp, 'WINDOW')
                        bpy.types.SpaceView3D.draw_handler_remove(self._handle_pointres, 'WINDOW')
                        context.scene['viparams']['vidisp'] = 'li'
                        context.area.tag_redraw()
                        return {'CANCELLED'}
                        
                    elif self.tablecomp.press and event.type == 'MOUSEMOVE':
                         self.tablecomp.move = 1
                         self.tablecomp.press = 0                     
                elif self.tablecomp.hl != (1, 1, 1, 1):
                    self.tablecomp.hl = (1, 1, 1, 1)
                    redraw = 1
                
            if context.scene['liparams']['unit'] in ('ASE (hrs)', 'sDA (%)', 'DA (%)', 'UDI-f (%)', 'UDI-s (%)', 'UDI-e (%)', 'UDI-a (%)', 'Max lux', 'Min lux', 'Ave lux', 'kWh', 'kWh/m2'):
                if self.dhscatter.frame != context.scene.frame_current:
                    self.dhscatter.update(context)
                    redraw = 1
                if self.dhscatter.unit != context.scene['liparams']['unit']:
                    self.dhscatter.update(context)
                    redraw = 1
                if self.dhscatter.cao != context.active_object:
                    self.dhscatter.update(context)
                    redraw = 1
                if self.dhscatter.col != context.scene.vi_leg_col:
                    self.dhscatter.update(context)
                    redraw = 1
                if context.scene['liparams']['unit'] in ('Max lux', 'Min lux', 'Ave lux', 'kWh', 'kWh/m2'):
                    if (self.dhscatter.vmin, self.dhscatter.vmax) != (context.scene.vi_scatter_min, context.scene.vi_scatter_max):
                       self.dhscatter.update(context) 
                       redraw = 1
                        
                
                if self.dhscatter.spos[0] < mx < self.dhscatter.epos[0] and self.dhscatter.spos[1] < my < self.dhscatter.epos[1]:
                    if self.dhscatter.hl != (0, 1, 1, 1):
                        self.dhscatter.hl = (0, 1, 1, 1)
                        redraw = 1 
                    if event.type == 'LEFTMOUSE':
                        if event.value == 'PRESS':
                            self.dhscatter.press = 1
                            self.dhscatter.move = 0
                            return {'RUNNING_MODAL'}
                        elif event.value == 'RELEASE':
                            if not self.dhscatter.move:
                                self.dhscatter.expand = 0 if self.dhscatter.expand else 1
                            self.dhscatter.press = 0
                            self.dhscatter.move = 0
                            context.area.tag_redraw()
                            return {'RUNNING_MODAL'}
                    
                    elif event.type == 'ESC':
                        bpy.types.SpaceView3D.draw_handler_remove(self._handle_disp, 'WINDOW')
                        bpy.types.SpaceView3D.draw_handler_remove(self._handle_pointres, 'WINDOW')
                        context.scene['viparams']['vidisp'] = 'li'
                        context.area.tag_redraw()
                        return {'CANCELLED'}
                        
                    elif self.dhscatter.press and event.type == 'MOUSEMOVE':
                         self.dhscatter.move = 1
                         self.dhscatter.press = 0   
                                            
                else:
                    if self.dhscatter.hl != (1, 1, 1, 1):
                        self.dhscatter.hl = (1, 1, 1, 1)
                        redraw = 1
                    if self.dhscatter.lspos[0] < mx < self.dhscatter.lepos[0] and self.dhscatter.lspos[1] < my < self.dhscatter.lepos[1] and abs(self.dhscatter.lepos[0] - mx) > 20 and abs(self.dhscatter.lspos[1] - my) > 20:
                        if self.dhscatter.expand: 
                            self.dhscatter.hl = (1, 1, 1, 1)
                            if event.type == 'LEFTMOUSE' and event.value == 'PRESS' and self.dhscatter.expand and self.dhscatter.lspos[0] < mx < self.dhscatter.lepos[0] and self.dhscatter.lspos[1] < my < self.dhscatter.lspos[1] + 0.9 * self.dhscatter.ydiff:
                                self.dhscatter.show_plot()
                                                         
            # Resize routines
            
            if abs(self.legend.lepos[0] - mx) < 20 and abs(self.legend.lspos[1] - my) < 20:
                self.legend.hl = (0, 1, 1, 1) 
                if event.type == 'LEFTMOUSE':
                    if event.value == 'PRESS':
                        self.legend.resize = 1
                    if self.legend.resize and event.value == 'RELEASE':
                        self.legend.resize = 0
                    return {'RUNNING_MODAL'}
                    
            elif abs(self.table.lepos[0] - mx) < 20 and abs(self.table.lspos[1] - my) < 20:
                self.table.hl = (0, 1, 1, 1) 
                if event.type == 'LEFTMOUSE':
                    if event.value == 'PRESS':
                        self.table.resize = 1
                    if self.table.resize and event.value == 'RELEASE':
                        self.table.resize = 0
                    return {'RUNNING_MODAL'}
            
            elif context.scene['viparams']['visimcontext'] == 'LiVi Compliance' and abs(self.tablecomp.lepos[0] - mx) < 20 and abs(self.tablecomp.lspos[1] - my) < 20:
                self.tablecomp.hl = (0, 1, 1, 1) 
                if event.type == 'LEFTMOUSE':
                    if event.value == 'PRESS':
                        self.tablecomp.resize = 1
                    if self.tablecomp.resize and event.value == 'RELEASE':
                        self.tablecomp.resize = 0
                    return {'RUNNING_MODAL'}

            elif context.scene['liparams']['unit'] in ('ASE (hrs)', 'sDA (%)', 'DA (%)', 'UDI-s (%)', 'UDI-e (%)', 'UDI-f (%)', 'UDI-a (%)', 'Max lux', 'Min lux', 'Ave lux', 'kWh', 'kWh/m2') and abs(self.dhscatter.lepos[0] - mx) < 20 and abs(self.dhscatter.lspos[1] - my) < 20:
                self.dhscatter.hl = (0, 1, 1, 1) 
                if event.type == 'LEFTMOUSE':
                    if event.value == 'PRESS':
                        self.dhscatter.resize = 1
                    if self.dhscatter.resize and event.value == 'RELEASE':
                        self.dhscatter.resize = 0
                    return {'RUNNING_MODAL'}
            # Move routines
                     
            if event.type == 'MOUSEMOVE':                
                if self.legend.move:
                    self.legend.pos = [mx, my]
                    redraw = 1
                if self.legend.resize:
                    self.legend.lepos[0], self.legend.lspos[1] = mx, my
                    redraw = 1
                if self.table.move:
                    self.table.pos = [mx, my]
                    redraw = 1
                if self.table.resize:
                    self.table.lepos[0], self.table.lspos[1] = mx, my
                    redraw = 1
                if context.scene['viparams']['visimcontext'] == 'LiVi Compliance':
                    if self.tablecomp.move:
                        self.tablecomp.pos = [mx, my]
                        redraw = 1
                    if self.tablecomp.resize:
                        self.tablecomp.lepos[0], self.tablecomp.lspos[1] = mx, my
                        redraw = 1
                try:
                    if self.dhscatter.move:
                        self.dhscatter.pos = [mx, my]
                        redraw = 1
                    if self.dhscatter.resize:
                        self.dhscatter.lepos[0], self.dhscatter.lspos[1] = mx, my
                        redraw = 1
                except:
                    pass
                                
            if redraw:
                context.area.tag_redraw()
                self.frame = context.scene.frame_current
        return {'PASS_THROUGH'}

    def invoke(self, context, event):
        scene = context.scene
        clearscene(scene, self)
        scene.vi_display = 1
        scene['viparams']['vidisp'] = 'lipanel'
        self.simnode = bpy.data.node_groups[context.scene['viparams']['restree']].nodes[context.scene['viparams']['resnode']]
        self.frame = context.scene.frame_current
        if li_display(self, self.simnode) == 'CANCELLED':
            return {'CANCELLED'}
        scene.vi_disp_wire, scene.vi_display = 1, 1
        lnd = linumdisplay(self, context, self.simnode)
        self._handle_pointres = bpy.types.SpaceView3D.draw_handler_add(lnd.draw, (context, ), 'WINDOW', 'POST_PIXEL')
        self.legend = basic_legend([80, context.region.height - 40], context.region.width, context.region.height, 'legend.png', 150, 600)
        self.legend.update(context)
#        self.dhscatter = wr_scatter([160, context.region.height - 40], context.region.width, context.region.height, 'stats.png', 600, 400)
#        if scene['viparams']['visimcontext'] == 'LiVi Basic':
        self.table = basic_table([240, context.region.height - 40], context.region.width, context.region.height, 'table.png', 600, 100)  
        self.table.update(context)
        if scene['viparams']['visimcontext'] == 'LiVi Compliance':
            self.tablecomp = comp_table([300, context.region.height - 40], context.region.width, context.region.height, 'compliance.png', 600, 200)
            self.tablecomp.update(context)
            if self.simnode['coptions']['canalysis'] == '3':
                self.dhscatter = leed_scatter([160, context.region.height - 40], context.region.width, context.region.height, 'scat.png', 600, 400)
                self.dhscatter.update(context)        
            self._handle_disp = bpy.types.SpaceView3D.draw_handler_add(comp_disp, (self, context, self.simnode), 'WINDOW', 'POST_PIXEL')

#        self.dhscatter.update(context)
        
#        self._handle_spnum = bpy.types.SpaceView3D.draw_handler_add(viwr_legend, (self, context, simnode), 'WINDOW', 'POST_PIXEL')
        elif scene['viparams']['visimcontext'] == 'LiVi Basic':
            self._handle_disp = bpy.types.SpaceView3D.draw_handler_add(basic_disp, (self, context, self.simnode), 'WINDOW', 'POST_PIXEL')
#        if scene['viparams']['visimcontext'] == 'LiVi Compliance':
#            self._handle_disp = bpy.types.SpaceView3D.draw_handler_add(comp_disp, (self, context, self.simnode), 'WINDOW', 'POST_PIXEL')
        elif scene['viparams']['visimcontext'] == 'LiVi CBDM':
            if self.simnode['coptions']['cbanalysis'] != '0':
                self.dhscatter = cbdm_scatter([160, context.region.height - 40], context.region.width, context.region.height, 'scat.png', 600, 400)
                self.dhscatter.update(context)
            self._handle_disp = bpy.types.SpaceView3D.draw_handler_add(cbdm_disp, (self, context, self.simnode), 'WINDOW', 'POST_PIXEL')
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

# Openfoam operators

class NODE_OT_Blockmesh(bpy.types.Operator):
    bl_idname = "node.blockmesh"
    bl_label = "Blockmesh export"
    bl_description = "Export an Openfoam blockmesh"
    bl_register = True
    bl_undo = True
    nodeid = bpy.props.StringProperty()

    def execute(self, context):
        scene = context.scene
        expnode = bpy.data.node_groups[self.nodeid.split('@')[1]].nodes[self.nodeid.split('@')[0]]
        bmos = [o for o in scene.objects if o.vi_type == '2']
        
        if viparams(self, scene):
            return {'CANCELLED'}        
        if len(bmos) != 1:
            ({'ERROR'},"One and only one object with the CFD Domain property is allowed")
            return {'ERROR'}
        with open(os.path.join(scene['viparams']['ofsfilebase'], 'controlDict'), 'w') as cdfile:
            cdfile.write(fvcdwrite("simpleFoam", 0.005, 5))
        with open(os.path.join(scene['viparams']['ofsfilebase'], 'fvSolution'), 'w') as fvsolfile:
            fvsolfile.write(fvsolwrite(expnode))
        with open(os.path.join(scene['viparams']['ofsfilebase'], 'fvSchemes'), 'w') as fvschfile:
            fvschfile.write(fvschwrite(expnode))
        with open(os.path.join(scene['viparams']['ofcpfilebase'], 'blockMeshDict'), 'w') as bmfile:
            bmfile.write(fvbmwrite(bmos[0], expnode))
        if not expnode.existing:
            call(("blockMesh", "-case", "{}".format(scene['viparams']['offilebase'])))
            fvblbmgen(bmos[0].data.materials, open(os.path.join(scene['viparams']['ofcpfilebase'], 'faces'), 'r'), open(os.path.join(scene['viparams']['ofcpfilebase'], 'points'), 'r'), open(os.path.join(scene['viparams']['ofcpfilebase'], 'boundary'), 'r'), 'blockMesh')
        else:
            pass

        expnode.export()
        return {'FINISHED'}

class NODE_OT_Snappymesh(bpy.types.Operator):
    bl_idname = "node.snappy"
    bl_label = "SnappyHexMesh export"
    bl_description = "Export an Openfoam snappyhexmesh"
    bl_register = True
    bl_undo = True
    nodeid = bpy.props.StringProperty()

    def execute(self, context):
        scene, mats = context.scene, []

        for dirname in os.listdir(scene['viparams']['offilebase']):
            if os.path.isdir(os.path.join(scene['viparams']['offilebase'], dirname)) and dirname not in ('0', 'constant', 'system'):
                shutil.rmtree(os.path.join(scene['viparams']['offilebase'], dirname))
        for fname in os.listdir(scene['viparams']['ofcpfilebase']):
            if os.path.isfile(os.path.join(scene['viparams']['ofcpfilebase'], fname)) and fname in ('cellLevel', 'pointLevel', 'surfaceIndex', 'level0Edge', 'refinementHistory'):
                os.remove(os.path.join(scene['viparams']['ofcpfilebase'], fname))

        expnode = bpy.data.node_groups[self.nodeid.split('@')[1]].nodes[self.nodeid.split('@')[0]]
        fvos = [o for o in scene.objects if o.vi_type == '3']
        if fvos:
            selobj(scene, fvos[0])
            bmos = [o for o in scene.objects if o.vi_type == '2']
#                bpy.ops.export_mesh.stl(filepath=os.path.join(scene['viparams']['ofctsfilebase'], '{}.obj'.format(o.name)), check_existing=False, filter_glob="*.stl", axis_forward='Y', axis_up='Z', global_scale=1.0, use_scene_unit=True, ascii=False, use_mesh_modifiers=True)
            fvobjwrite(scene, fvos[0], bmos[0])
#            bpy.ops.export_scene.obj(check_existing=True, filepath=os.path.join(scene['viparams']['ofctsfilebase'], '{}.obj'.format(fvos[0].name)), axis_forward='Y', axis_up='Z', filter_glob="*.obj;*.mtl", use_selection=True, use_animation=False, use_mesh_modifiers=True, use_edges=True, use_smooth_groups=False, use_smooth_groups_bitflags=False, use_normals=False, use_uvs=True, use_materials=True, use_triangles=True, use_nurbs=False, use_vertex_groups=False, use_blen_objects=True, group_by_object=False, group_by_material=True, keep_vertex_order=False, global_scale=1.0, path_mode='AUTO')
            gmats = [mat for mat in fvos[0].data.materials if mat.flovi_ground]
#            if gmats:
            with open(os.path.join(scene['viparams']['ofsfilebase'], 'snappyHexMeshDict'), 'w') as shmfile:
                shmfile.write(fvshmwrite(expnode, fvos[0], ground = gmats))
            with open(os.path.join(scene['viparams']['ofsfilebase'], 'meshQualityDict'), 'w') as mqfile:
                mqfile.write(fvmqwrite())
            with open(os.path.join(scene['viparams']['ofsfilebase'], 'surfaceFeatureExtractDict'), 'w') as sfefile:
                sfefile.write(fvsfewrite(fvos[0].name))
        call(('surfaceFeatureExtract', "-case", "{}".format(scene['viparams']['offilebase'])))
        call(('snappyHexMesh', "-overwrite", "-case", "{}".format(scene['viparams']['offilebase'])))
        for mat in fvos[0].data.materials:
#            mat.name = '{}_{}'.format(fvos[0].name, mat.name)
            mats.append(mat)
        for mat in [o for o in scene.objects if o.vi_type == '2'][0].data.materials:
            mats.append(mat)
        fvblbmgen(mats, open(os.path.join(scene['viparams']['ofcpfilebase'], 'faces'), 'r'), open(os.path.join(scene['viparams']['ofcpfilebase'], 'points'), 'r'), open(os.path.join(scene['viparams']['ofcpfilebase'], 'boundary'), 'r'), 'hexMesh')

        expnode.export()
        return {'FINISHED'}

class NODE_OT_FVSolve(bpy.types.Operator):
    bl_idname = "node.fvsolve"
    bl_label = "FloVi simulation"
    bl_description = "Solve an OpenFOAM case"
    bl_register = True
    bl_undo = True
    nodeid = bpy.props.StringProperty()

    def execute(self, context):
        scene = context.scene
        simnode = bpy.data.node_groups[self.nodeid.split('@')[1]].nodes[self.nodeid.split('@')[0]]
        bmos = [o for o in scene.objects if o.vi_type in ('2', '3')]
        with open(os.path.join(scene['viparams']['ofsfilebase'], 'controlDict'), 'w') as cdfile:
            cdfile.write(fvcdwrite(simnode.solver, simnode.dt, simnode.et))
        fvvarwrite(scene, bmos, simnode)
        with open(os.path.join(scene['viparams']['ofsfilebase'], 'fvSolution'), 'w') as fvsolfile:
            fvsolfile.write(fvsolwrite(simnode))
        with open(os.path.join(scene['viparams']['ofsfilebase'], 'fvSchemes'), 'w') as fvschfile:
            fvschfile.write(fvschwrite(simnode))
        with open(os.path.join(scene['viparams']['ofcfilebase'], 'transportProperties'), 'w') as fvtppfile:
            fvtppfile.write(fvtppwrite(simnode.solver))
        if simnode.solver != 'icoFoam':
            with open(os.path.join(scene['viparams']['ofcfilebase'], 'RASProperties'), 'w') as fvrasfile:
                fvrasfile.write(fvraswrite(simnode.turbulence))
        call((simnode.solver, "-case", "{}".format(scene['viparams']['offilebase'])))
        Popen(("paraFoam", "-case", "{}".format(scene['viparams']['offilebase'])))
        simnode.export()
        return {'FINISHED'}

class Gridify(bpy.types.Operator):
    ''''''
    bl_idname = "view3d.gridify"
    bl_label = "Gridify"
     
    def modal(self, context, event):
        scene = context.scene
        if self.upv != scene.gridifyup or self.us != scene.gridifyus or self.acs != context.scene.gridifyas or self.ft:
            self.bmnew = self.bm.copy()
            self.bmnew.transform(self.o.matrix_world)
            self.ft = 0
            self.upv = mathutils.Vector([x for x in context.scene.gridifyup])
            self.us = context.scene.gridifyus
            self.acs = context.scene.gridifyas
            self.bmnew.faces.ensure_lookup_table()
            self.bmnew.verts.ensure_lookup_table()
            norm = context.scene.gridifyup.normalized()
            norm2 = context.scene.gridifyup.normalized()
            vs = self.bmnew.verts[:]
            es = self.bmnew.edges[:]
            fs = [f for f in self.bmnew.faces[:] if self.o.data.materials[f.material_index] and self.o.data.materials[f.material_index].mattype == '1']
            gs = vs + es + fs 
            eul = mathutils.Euler(math.radians(-90) * fs[0].normal, 'XYZ')
            norm2.rotate(eul)         
            vertdots = [mathutils.Vector.dot(norm, vert.co) for vert in self.bmnew.verts]
            vertdots2 = [mathutils.Vector.dot(norm2, vert.co) for vert in self.bmnew.verts]
            svpos = self.bmnew.verts[vertdots.index(min(vertdots))].co
            svpos2 = self.bmnew.verts[vertdots2.index(min(vertdots2))].co
            res1, res2, ngs1, ngs2, gs1, gs2 = 1, 1, context.scene.gridifyus, context.scene.gridifyas, context.scene.gridifyus, context.scene.gridifyas
              
            while res1:
                res = bmesh.ops.bisect_plane(self.bmnew, geom = gs, dist = 0.001, plane_co = svpos + ngs1 * norm, plane_no = norm, use_snap_center = 0, clear_outer = 0, clear_inner = 0)
                res1 = res['geom_cut']
                gs = self.bmnew.verts[:] + self.bmnew.edges[:] + [v for v in res['geom'] if isinstance(v, bmesh.types.BMFace)]
                ngs1 += gs1
        
            while res2:
                res = bmesh.ops.bisect_plane(self.bmnew, geom = gs, dist = 0.001, plane_co = svpos2 + ngs2 * norm2, plane_no = norm2, use_snap_center = 0, clear_outer = 0, clear_inner = 0)
                res2 = res['geom_cut']
                gs = self.bmnew.verts[:] + self.bmnew.edges[:] + [v for v in res['geom'] if isinstance(v, bmesh.types.BMFace)]
                ngs2 += gs2
             
            self.bmnew.transform(self.o.matrix_world.inverted())
            self.bmnew.to_mesh(self.o.data)
#            bmesh.update_edit_mesh(self.o.data)
            self.o.data.update()
            self.bmnew.free()
            context.area.tag_redraw()
            return {'RUNNING_MODAL'}

        elif event.type == 'ESC':  
            self.bm.to_mesh(self.o.data)
#            bmesh.update_edit_mesh(self.o.data, tessface=False, destructive=True)
            context.area.tag_redraw()
            return {'CANCELLED'}

        elif event.ctrl and event.type == 'RET':
            return {'FINISHED'}
            
        else:
            return {'PASS_THROUGH'}
     
    def invoke(self, context, event):
        scene = context.scene
        self.o = bpy.context.active_object
        if self.o.data.materials:
            self.bm = bmesh.new()
            tm = self.o.to_mesh(scene = scene, apply_modifiers = True, settings = 'PREVIEW')
            self.bm.from_mesh(tm)
#            self.bm = bmesh.from_edit_mesh(self.o.data)
            bpy.data.meshes.remove(tm)
            self.ft = 1
            self.upv = mathutils.Vector([x for x in scene.gridifyup])
            self.us = scene.gridifyus
            self.acs = scene.gridifyas
            context.window_manager.modal_handler_add(self)
            return {'RUNNING_MODAL'}
        else:
            self.report({'ERROR'}, "No materials associated with object")
            return {'CANCELLED'}
 

#class VIEW3D_OT_SPTime(bpy.types.Operator):
#    '''Display results legend and stats in the 3D View'''
#    bl_idname = "view3d.sptimeisplay"
#    bl_label = "Point numbers"
#    bl_description = "Display the current solar time on the sunpath"
#    bl_register = True
#    bl_undo = True
#
#    def modal(self, context, event):
#        scene = context.scene
#        if context.area:
#            context.area.tag_redraw()
#        if scene.vi_display == 0 or scene['viparams']['vidisp'] != 'sp':
#            bpy.types.SpaceView3D.draw_handler_remove(self._handle_sptime, 'WINDOW')
#            [scene.objects.unlink(o) for o in scene.objects if o.get('VIType') and o['VIType'] in ('SunMesh', 'SkyMesh')]
#            return {'CANCELLED'}
#        return {'PASS_THROUGH'}
#
#    def invoke(self, context, event):
#        scene = context.scene
#        simnode = bpy.data.node_groups[scene['viparams']['restree']].nodes[scene['viparams']['resnode']]
#        self._handle_sptime = bpy.types.SpaceView3D.draw_handler_add(sptimedisplay, (self, context, simnode), 'WINDOW', 'POST_PIXEL')
#        context.window_manager.modal_handler_add(self)
#        scene.vi_display = 1
#        return {'RUNNING_MODAL'}