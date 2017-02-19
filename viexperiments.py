# -*- coding: utf-8 -*-
"""
Created on Sat Apr  2 22:34:13 2016

@author: ryan
"""

bl_info = {
    "name": "VI-Suite Experiments",
    "author": "Ryan Southall",
    "version": (0, 4, 0),
    "blender": (2, 7, 7),
    "api":"",
    "location": "Node Editor & 3D View > Properties Panel",
    "description": "Radiance/EnergyPlus exporter and results visualiser",
    "warning": "This is a beta script. Some functionality is buggy",
    "wiki_url": "",
    "tracker_url": "",
    "category": "Import-Export"}
    
import bpy, bgl, blf, os, colorsys, sys
from math import sin, pi, log10, ceil
import matplotlib
matplotlib.use('Qt5Agg', force = True)
from matplotlib.collections import PatchCollection
import matplotlib.ticker as ticker

import matplotlib.cm as mcm
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from numpy import add as nadd
from numpy import log10 as nlog10
from numpy import array, where, repeat, flipud, fliplr
import numpy as np
from matplotlib.patches import Wedge, Circle, Rectangle
import math
from xml.dom import minidom
from numpy import max as amax
from numpy import min as amin

coldict = {'0': 'rainbow', '1': 'gray', '2': 'hot', '3': 'CMRmap', '4': 'jet', '5': 'plasma'}
resdict = {'LiVi CBDM':'livires', 'EnVi':'envires'}
restypedict = {'0': 'daarea', '1':'sdaarea', '2':'udilarea', '3':'udisarea', '4': 'udiaarea', '5':'udiharea', '6':'asearea'}
titledict = {'0': 'Daylight Autonomous Area (%)', '1':'Spatial Daylight Autonomous Area (%)', '2':'UDI-Low Area (%)', '3':'UDI-Supplemental Area (%)', '4': 'UDI-Autonomous Area (%)', '5':'UDI-Excess Area (%)', '6':'Sunlight Overexposure Area (%)'}
daydict = {'envires': 'envi_days', 'livires': 'cbdm_days'}
hourdict = {'envires': 'envi_hours', 'livires': 'cbdm_hours'}
kfsa = array([0.02391, 0.02377, 0.02341, 0.02738, 0.02933, 0.03496, 0.04787, 0.05180, 0.13552])
kfact = array([0.9981, 0.9811, 0.9361, 0.8627, 0.7631, 0.6403, 0.4981, 0.3407, 0.1294])

def retdp(context, mres):
    try:
        dplaces = 0 if ceil(log10(100/mres)) < 0 or context.scene['viparams']['resnode'] == 'VI Sun Path' else ceil(log10(100/mres))
    except:
        dplaces = 0
    return dplaces

class Exper3DPanel(bpy.types.Panel):
    '''VI-Suite 3D view panel'''
    bl_label = "Exper Display"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
        
    def draw(self, context):
        layout = self.layout
        row = layout.row()    
        row.operator("view3d.cbdm_display", text="CBDM Display")
        row.operator("view3d.bsdf_display", text="BSDF Display")
        row.operator("view3d.bsdf2_display", text="BSDF2 Display")
        row = layout.row()
        row.prop(context.scene, 'vi_leg_col')
        row.prop(context.scene, 'bsdf_leg_max')
        row.prop(context.scene, 'bsdf_leg_min')
        
#class VIEW3D_OT_En_Disp(bpy.types.Operator):
#    bl_idname = "view3d.en_display"
#    bl_label = "EnergyPlus display"
#    bl_description = "Display EnergyPlus Result Metrics"
#    bl_register = True
#    bl_undo = False
#    
#    def invoke(self, context, event, resnode):
#        scene = context.scene
#        rl = resnode['reslists']
#        zrl = list(zip(*rl))
#        reszones = [o.name.upper() for o in bpy.data.objects if o.name.upper() in zrl[2]]
#        if not reszones:
#            self.report({'ERROR'},"There are no EnVi results to display")
#            return {'CANCELLED'}
#        
#        if not bpy.context.active_object or 'EN_'+bpy.context.active_object.name.upper() not in reszones:
#            return
#        if cao and cao.active_material.get('bsdf') and cao.active_material['bsdf']['xml']:
#            width, height = context.region.width, context.region.height
#            self.bsdf = bsdf(context, width, height)
#            self.bsdfpress, self.bsdfmove, self.bsdfresize = 0, 0, 0
#            self._handle_bsdf_disp = bpy.types.SpaceView3D.draw_handler_add(bsdf_disp, (self, context), 'WINDOW', 'POST_PIXEL')
#            context.window_manager.modal_handler_add(self)
#            context.area.tag_redraw()            
#            return {'RUNNING_MODAL'}
#        else:
#            self.report({'ERROR'},"Selected object contains no BSDF information")
#            return {'CANCELLED'}

class VIEW3D_OT_BSDF2_Disp(bpy.types.Operator):
    bl_idname = "view3d.bsdf2_display"
    bl_label = "BSDF2 display"
    bl_description = "Display BSDF2"
    bl_register = True
    bl_undo = False
    
    def modal(self, context, event): 
        if context.region and context.area.type == 'VIEW_3D' and context.region.type == 'WINDOW': 
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
                    bpy.data.images.remove(self.bsdf.image)
                    self.bsdf.plt.close()
                    bpy.types.SpaceView3D.draw_handler_remove(self._handle_bsdf_disp, 'WINDOW')
                    context.area.tag_redraw()
                    return {'CANCELLED'}
                    
                elif self.bsdfpress and event.type == 'MOUSEMOVE':
                     self.bsdfmove = 1
                     self.bsdfpress = 0
                            
            elif abs(self.bsdf.gepos[0] - mx) < 10 and abs(self.bsdf.gspos[1] - my) < 10:
                self.bsdf.hl = (0, 1, 1, 1) 
                if event.type == 'LEFTMOUSE':
                    if event.value == 'PRESS':
                        self.bsdf.resize = 1
                    if self.bsdf.resize and event.value == 'RELEASE':
                        self.bsdf.resize = 0
                    return {'RUNNING_MODAL'}  
            
            elif self.bsdf.gspos[0] + 0.45 * self.bsdf.xdiff < mx < self.bsdf.gspos[0] + 0.8 * self.bsdf.xdiff and self.bsdf.gspos[1] + 0.06 * self.bsdf.ydiff < my < self.bsdf.gepos[1] - 5:
                if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
                    self.bsdf.plt.show()
            
            else:
                for butrange in self.bsdf.buttons:
                    if self.bsdf.buttons[butrange][0] - 0.0075 * self.bsdf.xdiff < mx < self.bsdf.buttons[butrange][0] + 0.0075 * self.bsdf.xdiff and self.bsdf.buttons[butrange][1] - 0.01 * self.bsdf.ydiff < my < self.bsdf.buttons[butrange][1] + 0.01 * self.bsdf.ydiff:
                        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
                            if butrange in ('Front', 'Back'):
                                self.bsdf.dir_select = butrange
                            elif butrange in ('Visible', 'Solar', 'Discrete'):
                                self.bsdf.rad_select = butrange
                            elif butrange in ('Transmission', 'Reflection'):
                                self.bsdf.type_select = butrange
                            elif butrange in ('Log', 'Linear'):
                                self.bsdf.scale_select = butrange
#                            self.bsdf.plot(context.scene)
#                            self.bsdf.save(context.scene)

                self.bsdf.hl = (1, 1, 1, 1)
                                
            if event.type == 'MOUSEMOVE':                
                if self.bsdfmove:
                    self.bsdf.pos = [mx, my]
                if self.bsdf.resize:
                    self.bsdf.gepos[0], self.bsdf.gspos[1] = mx, my
            
            if self.bsdf.expand and self.bsdf.gspos[0] < mx < self.bsdf.gepos[0] and self.bsdf.gspos[1] < my < self.bsdf.gepos[1]:
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
#                        self.bsdf.plot(context.scene)
#                        self.bsdf.save(context.scene)
                else:
                    self.bsdf.patch_hl = None
                    
            if self.bsdf.leg_max != context.scene.bsdf_leg_max or self.bsdf.leg_min != context.scene.bsdf_leg_min or self.bsdf.col != coldict[context.scene.vi_leg_col]:
                self.bsdf.col = coldict[context.scene.vi_leg_col]
                self.bsdf.leg_max = context.scene.bsdf_leg_max
                self.bsdf.leg_min = context.scene.bsdf_leg_min
#                self.bsdf.plot(context.scene)
#                self.bsdf.save(context.scene)
            
            context.area.tag_redraw()
        
        return {'PASS_THROUGH'}
        
    def invoke(self, context, event):
        cao = context.active_object
        if cao and cao.active_material.get('bsdf') and cao.active_material['bsdf']['xml']:
            width, height = context.region.width, context.region.height
            self.bsdf = bsdf2(context, width, height)
            self.bsdfpress, self.bsdfmove, self.bsdfresize = 0, 0, 0
            self._handle_bsdf_disp = bpy.types.SpaceView3D.draw_handler_add(bsdf2_disp, (self, context), 'WINDOW', 'POST_PIXEL')
            context.window_manager.modal_handler_add(self)
            context.area.tag_redraw()            
            return {'RUNNING_MODAL'}
        else:
            self.report({'ERROR'},"Selected material contains no BSDF information")
            return {'CANCELLED'}
        
class VIEW3D_OT_BSDF_Disp(bpy.types.Operator):
    bl_idname = "view3d.bsdf_display"
    bl_label = "BSDF display"
    bl_description = "Display BSDF"
    bl_register = True
    bl_undo = False
        
    def modal(self, context, event): 
        if context.region and context.area.type == 'VIEW_3D' and context.region.type == 'WINDOW': 
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
                    bpy.data.images.remove(self.bsdf.image)
                    self.bsdf.plt.close()
                    bpy.types.SpaceView3D.draw_handler_remove(self._handle_bsdf_disp, 'WINDOW')
                    context.area.tag_redraw()
                    return {'CANCELLED'}
                    
                elif self.bsdfpress and event.type == 'MOUSEMOVE':
                     self.bsdfmove = 1
                     self.bsdfpress = 0
                            
            elif abs(self.bsdf.gepos[0] - mx) < 10 and abs(self.bsdf.gspos[1] - my) < 10:
                self.bsdf.hl = (0, 1, 1, 1) 
                if event.type == 'LEFTMOUSE':
                    if event.value == 'PRESS':
                        self.bsdf.resize = 1
                    if self.bsdf.resize and event.value == 'RELEASE':
                        self.bsdf.resize = 0
                    return {'RUNNING_MODAL'}  
            
            elif self.bsdf.gspos[0] + 0.45 * self.bsdf.xdiff < mx < self.bsdf.gspos[0] + 0.8 * self.bsdf.xdiff and self.bsdf.gspos[1] + 0.06 * self.bsdf.ydiff < my < self.bsdf.gepos[1] - 5:
                if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
                    self.bsdf.plt.show()
            
            else:
                for butrange in self.bsdf.buttons:
                    if self.bsdf.buttons[butrange][0] - 0.0075 * self.bsdf.xdiff < mx < self.bsdf.buttons[butrange][0] + 0.0075 * self.bsdf.xdiff and self.bsdf.buttons[butrange][1] - 0.01 * self.bsdf.ydiff < my < self.bsdf.buttons[butrange][1] + 0.01 * self.bsdf.ydiff:
                        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
                            if butrange in ('Front', 'Back'):
                                self.bsdf.dir_select = butrange
                            elif butrange in ('Visible', 'Solar', 'Discrete'):
                                self.bsdf.rad_select = butrange
                            elif butrange in ('Transmission', 'Reflection'):
                                self.bsdf.type_select = butrange
                            elif butrange in ('Log', 'Linear'):
                                self.bsdf.scale_select = butrange
                            self.bsdf.plot(context.scene)
                            self.bsdf.save(context.scene)

                self.bsdf.hl = (1, 1, 1, 1)
                                
            if event.type == 'MOUSEMOVE':                
                if self.bsdfmove:
                    self.bsdf.pos = [mx, my]
                if self.bsdf.resize:
                    self.bsdf.gepos[0], self.bsdf.gspos[1] = mx, my
            
            if self.bsdf.expand and self.bsdf.gspos[0] < mx < self.bsdf.gepos[0] and self.bsdf.gspos[1] < my < self.bsdf.gepos[1]:
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
                        self.bsdf.plot(context.scene)
                        self.bsdf.save(context.scene)
                else:
                    self.bsdf.patch_hl = None
                    
            if self.bsdf.leg_max != context.scene.bsdf_leg_max or self.bsdf.leg_min != context.scene.bsdf_leg_min or self.bsdf.col != coldict[context.scene.vi_leg_col]:
                self.bsdf.col = coldict[context.scene.vi_leg_col]
                self.bsdf.leg_max = context.scene.bsdf_leg_max
                self.bsdf.leg_min = context.scene.bsdf_leg_min
                self.bsdf.plot(context.scene)
                self.bsdf.save(context.scene)
            
            context.area.tag_redraw()
        
        return {'PASS_THROUGH'}
                
    def invoke(self, context, event):
        cao = context.active_object
        if cao and cao.active_material.get('bsdf') and cao.active_material['bsdf']['xml']:
            width, height = context.region.width, context.region.height
            self.bsdf = bsdf(context, width, height)
            self.bsdfpress, self.bsdfmove, self.bsdfresize = 0, 0, 0
            self._handle_bsdf_disp = bpy.types.SpaceView3D.draw_handler_add(bsdf_disp, (self, context), 'WINDOW', 'POST_PIXEL')
            context.window_manager.modal_handler_add(self)
            context.area.tag_redraw()            
            return {'RUNNING_MODAL'}
        else:
            self.report({'ERROR'},"Selected material contains no BSDF information")
            return {'CANCELLED'}
            
class VIEW3D_OT_Basic_Disp(bpy.types.Operator):
    bl_idname = "view3d.basic_display"
    bl_label = "Basic display"
    bl_description = "Display LiVi Basic metrics"
    bl_register = True
    bl_undo = False
    _handle = None
    disp =  bpy.props.IntProperty(default = 1)
    
    def modal(self, context, event):  
        mx, my = event.mouse_region_x, event.mouse_region_y
        if self.legend.spos[0] < mx < self.legend.epos[0] and 0.95 * (self.legend.epos[1] - self.legend.spos[1]) < my < self.legend.epos[1]:
            if event.type == 'LEFTMOUSE':
                if event.value == 'PRESS':
                    self.legpress = 1
                elif event.type == 'RELEASE':
                    self.legpress = 0
                    
                return {'RUNNING_MODAL'}
        
        elif self.table.spos[0] < mx < self.table.epos[0] and self.table.spos[1] < my < self.table.epos[1]:
            if event.type == 'LEFTMOUSE':
                if event.value == 'PRESS':
                    self.tablepress = 1
                elif event.value == 'RELEASE':
                    self.tablepress = 0
                return {'RUNNING_MODAL'}
    
class VIEW3D_OT_CBDM_Disp(bpy.types.Operator):
    bl_idname = "view3d.cbdm_display"
    bl_label = "CBDM display"
    bl_description = "Display the results on the sensor surfaces"
    bl_register = True
    bl_undo = False
    _handle = None
    disp =  bpy.props.IntProperty(default = 1)
    
    def modal(self, context, event):
        if event.type in {'RIGHTMOUSE', 'ESC'}:
            bpy.data.images.remove(self.scatter.image)
            bpy.types.SpaceView3D.draw_handler_remove(self._handle_cbdm_disp, 'WINDOW')
            context.area.tag_redraw()
            return {'CANCELLED'}

        if context.region and context.area.type == 'VIEW_3D' and context.region.type == 'WINDOW': 
            scene = context.scene
            mx, my = event.mouse_region_x, event.mouse_region_y
            currob = context.active_object 
            vicon = context.scene['viparams']['visimcontext']
            
            if self.legend.spos[0] < mx < self.legend.epos[0] and self.legend.epos[1] - 0.1 * (self.legend.epos[1] - self.legend.spos[1]) < my < self.legend.epos[1]:
                if event.type == 'WHEELUPMOUSE':
                    scene.vi_leg_max += scene.vi_leg_max * 0.05
                    return {'RUNNING_MODAL'}
                if event.type == 'WHEELDOWNMOUSE':
                    scene.vi_leg_max -= (scene.vi_leg_max - scene.vi_leg_min) * 0.05
                    return {'RUNNING_MODAL'}
            elif self.legend.spos[0] < mx < self.legend.epos[0] and self.legend.spos[1] < my < self.legend.spos[1] + 0.05 * (self.legend.epos[1] - self.legend.spos[1]):
                if event.type == 'WHEELUPMOUSE':
                    scene.vi_leg_min += (scene.vi_leg_max - scene.vi_leg_min) * 0.05
                    return {'RUNNING_MODAL'}
                if event.type == 'WHEELDOWNMOUSE':
                    scene.vi_leg_min -= scene.vi_leg_min * 0.05
                    return {'RUNNING_MODAL'}

            if currob and self.scatter.oname != currob.name and currob.get('livires') or scene.li_disp_da != self.scatter.unit:
                self.scatter.unit = scene.li_disp_da
                self.scatter.oname = currob.name
                self.scatter.scattergraph(context, currob['livires']['cbdm_days'], currob['livires']['cbdm_hours'], currob['livires'][restypedict[context.scene.li_disp_da]], currob.name + ' ' + titledict[context.scene.li_disp_da], 'Day', 'Hour', scene['liparams']['unit'])
                self.scatter.savegraph(context.scene)

            elif currob and currob.name not in self.scatter.resonames and self.scatter.oname in self.scatter.resonames:
                self.scatter.oname = currob.name
                resobs = [o for o in context.scene.objects if vicon in resdict and o.get(resdict[vicon]) and o.licalc]
                res = [o[resdict[vicon]][restypedict[context.scene.li_disp_da]] for o in resobs]
                res = nadd(*res)/len(res) if len(res) > 1 else res
                self.scatter.scattergraph(context, resobs[0][resdict[vicon]]['cbdm_days'], resobs[0][resdict[vicon]]['cbdm_hours'], res, 'All '+ titledict[context.scene.li_disp_da], 'Day', 'Hour', scene['liparams']['unit'])
                self.scatter.savegraph(context.scene)
                            
            if self.legend.spos[0] < mx < self.legend.epos[0] and self.legend.spos[1] < my < self.legend.epos[1]:
                if event.type == 'LEFTMOUSE':
                    if event.value == 'PRESS':
                        self.legpress = 1
                    if event.type == 'RELEASE':
                        self.legpress = 0                        
                    return {'RUNNING_MODAL'}
                
            elif self.scatter.spos[0] < mx < self.scatter.epos[0] and self.scatter.spos[1] < my < self.scatter.epos[1]:
                self.scatter.hl = (0, 1, 1, 1)  
                if event.type == 'LEFTMOUSE':
                    if event.value == 'PRESS':
                        self.scatterpress = 1
                        self.scattermove = 0
                        return {'RUNNING_MODAL'}
                    elif event.value == 'RELEASE':
                        if not self.scattermove:
                            self.scatter.expand = 0 if self.scatter.expand else 1
                        self.scatterpress = 0
                        self.scattermove = 0
                        context.area.tag_redraw()
                        return {'RUNNING_MODAL'}
                elif self.scatterpress and event.type == 'MOUSEMOVE':
                     self.scattermove = 1
                     self.scatterpress = 0
        
            elif self.table.spos[0] < mx < self.table.epos[0] and self.table.spos[1] < my < self.table.epos[1]: 
                self.table.hl = (0, 1, 1, 1)
                if event.type == 'LEFTMOUSE':
                    if event.value == 'PRESS':
                        self.tablepress = 1
                        self.tablemove = 0
                        return {'RUNNING_MODAL'}
                    elif event.value == 'RELEASE':
                        if not self.tablemove:
                            self.table.expand = 0 if self.table.expand else 1
                        self.tablepress = 0
                        self.tablemove = 0
                        context.area.tag_redraw()
                        return {'RUNNING_MODAL'}
                elif self.tablepress and event.type == 'MOUSEMOVE':
                    self.tablemove = 1
                    self.tablepress = 0                      
            else:  
                self.scatter.hl = (1, 1, 1, 1)
                self.table.hl = (1, 1, 1, 1)

            if event.type == 'MOUSEMOVE':
                if self.tablemove:
                    self.table.pos = [mx, my]
                elif self.scattermove:
                    self.scatter.pos = [mx, my]
                elif self.legpress:
                    self.legend.pos = [mx, my] 
                
            if self.scatter.expand:
                if self.scatter.gspos[0] < mx < self.scatter.gepos[0] and self.scatter.gspos[1] < my < self.scatter.gepos[1]:
                    if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
                        self.scatter.plt.show()                       
                        return{'RUNNING_MODAL'}

            context.area.tag_redraw()
        return {'PASS_THROUGH'}

    def invoke(self, context, event):
        width, height = context.region.width, context.region.height
        self.legend = legend(context, width, height)
        self.scatter = dhscatter(context, width, height)
        self.table = table(context, width, height)
        self.tablepress, self.tablemove, self.scatterpress, self.scattermove, self.legpress, self.lmb = 0, 0, 0, 0, 0, 0
        self._handle_cbdm_disp = bpy.types.SpaceView3D.draw_handler_add(cbdm_disp, (self, context), 'WINDOW', 'POST_PIXEL')
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}
        
def drawsquarepoly(x1, y1, x2, y2, r, g, b, a):
#    bgl.glEnable(bgl.GL_BLEND)
    bgl.glColor4f(r, g, b, a)
    bgl.glBegin(bgl.GL_POLYGON)
    bgl.glVertex2i(x1, y2)
    bgl.glVertex2i(x2, y2)
    bgl.glVertex2i(x2, y1)
    bgl.glVertex2i(x1, y1)
    bgl.glEnd()
#    bgl.glDisable(bgl.GL_BLEND)
    
def drawsquareloop(x1, y1, x2, y2):
    bgl.glColor4f(0.0, 0.0, 0.0, 1.0)
    bgl.glBegin(bgl.GL_LINE_LOOP)
    bgl.glVertex2i(x1, y2)
    bgl.glVertex2i(x2, y2)
    bgl.glVertex2i(x2, y1)
    bgl.glVertex2i(x1, y1)
    bgl.glEnd()
    
def drawloop(verts):
    bgl.glColor4f(0.0, 0.0, 0.0, 1.0)
    bgl.glBegin(bgl.GL_LINE_LOOP)
    for vert in verts:
        bgl.glVertex2i(vert)
    bgl.glEnd()
    
class visbar():
    def __init__(self, pops):
#        self.spos = [int(0.05 * width), int(0.1 * height)]
#        self.epos = [int(0.1 * width), int(0.9 * height)]
        self.pops = pops
        
    def visadd(self, vis):
        if vis not in self.pops:
            self.pops.append(vis)

    def visrem(self, vis):
        if vis in self.pops:
            self.pops.remove(vis)
            
    def draw(self, width, height):
        self.width = 50 if width / 10 < 50 else width
        self.popsizex = width * 0.8
        self.popsizey = height * 0.8 / 10 if len(self.pops) <= 10 else height * 0.8 / len(self.pops)
        self.height = len(self.pops) * self.popsizey
        self.cpos = [width * 0.05 + 0.5 * self.width, 0.5 * height]
        xdiff, ydiff = self.width * 0.45, self.height * 0.5 - self.width * 0.45
        corners = [[self.cpos[0] - xdiff, self.cpos[1] + ydiff], [self.cpos[0] + xdiff, self.cpos[1] + ydiff], [self.cpos[0] + xdiff, self.cpos[1] - ydiff], [self.cpos[0] - xdiff, self.cpos[1] - ydiff]]
        verts = [[corners[0][0] - self.width * 0.05 * math.cos(a), corners[0][1] + self.width * 0.05 * math.sin(a)] for a in range(0, 90, 10)] + \
                [[corners[1][0] + self.width * 0.05 * math.cos(a), corners[1][1] + self.width * 0.05 * math.sin(a)] for a in range(0, 90, 10)] + \
                [[corners[2][0] + self.width * 0.05 * math.cos(a), corners[2][1] - self.width * 0.05 * math.sin(a)] for a in range(0, 90, 10)] + \
                [[corners[3][0] - self.width * 0.05 * math.cos(a), corners[3][1] - self.width * 0.05 * math.sin(a)] for a in range(0, 90, 10)]
        drawloop(verts)
    
class legend():
    def __init__(self, context, width, height):
        self.spos = [int(0.05 * width), int(0.1 * height)]
        self.epos = [int(0.1 * width), int(0.9 * height)]
        
    def draw(self, context, width, height):
        scene = context.scene
        if not scene.get('liparams'):
            scene.vi_display = 0
            return
        if scene.frame_current not in range(scene['liparams']['fs'], scene['liparams']['fe'] + 1) or not scene.vi_leg_display  or not any([o.lires for o in scene.objects]) or scene['liparams']['unit'] == 'Sky View':
            return
        fc = str(scene.frame_current)
        dplaces = retdp(context, scene.vi_leg_max)
        resvals = [format(scene.vi_leg_min + i*(scene.vi_leg_max - scene.vi_leg_min)/19, '.{}f'.format(dplaces)) for i in range(20)] if scene.vi_leg_scale == '0' else \
                        [format(scene.vi_leg_min + (1 - log10(i)/log10(20))*(scene.vi_leg_max - scene.vi_leg_min), '.{}f'.format(dplaces)) for i in range(1, 21)[::-1]]
        lenres = len(resvals[-1])
        font_id = 0
        blf.enable(0, 4)
        blf.enable(0, 8)
        blf.shadow(font_id, 5, 0.7, 0.7, 0.7, 1)
    #    blf.blur(font_id, 2)
        blf.size(font_id, 44, int(height * 0.05))
        mdimen = max(2 * blf.dimensions(font_id, resvals[-1])[0], blf.dimensions(font_id, scene['liparams']['unit'])[0]) + int(width * 0.01)
        self.spos = [int(0.05 * width), int(0.1 * height)] 
        self.epos = [int(self.spos[0] + mdimen), int(0.9 * height)]
        lspos = [self.spos[0], self.spos[1]]# + 0.1 * (self.epos[1] - self.spos[1])]
        lepos = [self.epos[0], self.epos[1] - 0.05 * (self.epos[1] - self.spos[1])]
        lwidth = lepos[0] - lspos[0]
        lheight = lepos[1] - lspos[1]
        drawpoly(self.spos[0], self.spos[1], self.epos[0], self.epos[1], 0.9, 1, 1, 1)
        drawloop(self.spos[0], self.spos[1], self.epos[0], self.epos[1])
        blf.position(font_id, lspos[0] + (lwidth - blf.dimensions(font_id, scene['liparams']['unit'])[0]) * 0.5, lepos[1] + (0.05 * (self.epos[1] - self.spos[1]) - blf.dimensions(font_id, 'Lux')[1]) * 0.5, 0)
#        drawfont(scene['liparams']['unit'], font_id, 0, height, 25, 57)        
        blf.draw(font_id, scene['liparams']['unit'])
    #    blf.enable(0, blf.SHADOW)
    #    blf.enable(0, blf.KERNING_DEFAULT)
    #    blf.shadow(0, 5, 0, 0, 0, 0.7)
        bgl.glLineWidth(1)
        bgl.glColor4f(*scene.vi_display_rp_fc)

        blf.shadow(font_id, 5, *scene.vi_display_rp_fsh)
        cols = retcols(scene)
        for i in range(20):
            num = resvals[i]
            rgba = cols[i]
            drawpoly(lspos[0], int(lspos[1] + i * lheight/20), int(lspos[0] + lwidth * 0.4), int(lspos[1] + (i + 1) * lheight/20), *rgba)    
            drawloop(lspos[0], int(lspos[1] + i * lheight/20), int(lspos[0] + lwidth * 0.4), int(lspos[1] + (i + 1) * lheight/20))
            drawloop(int(lspos[0] + lwidth * 0.4), int(lspos[1] + i * lheight/20), lepos[0], int(lspos[1] + (i + 1) * lheight/20))                
            bgl.glHint(bgl.GL_LINE_SMOOTH_HINT, bgl.GL_NICEST)            
            blf.size(font_id, 14, int((lepos[1] - lspos[1]) * 0.2))
            ndimen = blf.dimensions(font_id, "{}".format(num))
            blf.position(font_id, int(lepos[0] - mdimen * 0.075 - ndimen[0]), int(lspos[1] + i * lheight/20) + int((lheight/20 - ndimen[1])*0.5), 0)
            bgl.glColor4f(*scene.vi_display_rp_fc)
            blf.draw(font_id, "{}".format(resvals[i]))
    bgl.glColor4f(0, 0, 0, 1)
    blf.disable(0, 8)  
    blf.disable(0, 4)

def retcols(scene):
    try:
        cmap = mcm.get_cmap(scene.vi_leg_col)
        hs = [0.75 - 0.75*(i/19) for i in range(20)]
        rgbas = [cmap(int(i * 256/(20 - 1))) for i in range(20)]
#        if scene.vi_leg_col == '0':
#            hs = [0.75 - 0.75*(i/19) for i in range(levels)]
#            rgbas = [(*colorsys.hsv_to_rgb(h, 1.0, 1.0), 1.0) for h in hs]
#        elif scene.vi_leg_col == '1':
#            rgbas = [(i/19, i/19, i/19, 1) for i in range(levels)]
#        elif scene.vi_leg_col == '2':
#            rgbas = [mcm.hot(int(i * 256/19)) for i in range(levels)]
#        elif scene.vi_leg_col == '3':
#            rgbas = [mcm.CMRmap(int(i * 256/19)) for i in range(levels)]
#        elif scene.vi_leg_col == '4':
#            rgbas = [mcm.jet(int(i * 256/19)) for i in range(levels)]
#        elif scene.vi_leg_col == '5':
#            rgbas = [mcm.plasma(int(i * 256/19)) for i in range(levels)]
    except:
        hs = [0.75 - 0.75*(i/19) for i in range(20)]
        rgbas = [(*colorsys.hsv_to_rgb(h, 1.0, 1.0), 1.0) for h in hs]
    return rgbas
    
def sinebow(h):
  h += 1/2
  h *= -1
  r = sin(pi * h)
  g = sin(pi * (h + 1/3))
  b = sin(pi * (h + 2/3))
  return (chan**2 for chan in (r, g, b))
  
class bargraph():
    def __init__(self, context, width, height):
        self.plt = plt
#        self.fig = self.plt.figure()
        self.oname = context.active_object.name if context.active_object else ''
        self.spos = [int(0.15 * width), int(0.175 * height)]
        self.epos = [int(0.9 * width), int(0.925 * height)]
        self.gspos = [int(0.15 * width), int(0.65 * height)]
        self.gepos = [int(0.5 * width), int(0.9 * height)]
        self.pos = [0.3 * width, 0.9 * height]
        self.gpos = (self.pos[0] + 0.2 * width, self.pos[1] - 0.2 * height)        
        self.hl = (1, 1, 1, 1)
        self.expand = 0
        self.image = bpy.data.images.load('/home/ryan/.config/blender/2.77/scripts/addons/vi-suite04/images/stats.png') 
        self.image.user_clear()
        self.barloc = os.path.join(context.scene['viparams']['newdir'], 'images', 'bar.png') 
        self.vicon = context.scene['viparams']['visimcontext']
        
    def bargraph(self, context):
        self.plt.clf()
        self.plt.close()
        
        try:
            width = (context.active_object['livires']['valbins'][1] - context.active_object['livires']['valbins'][0]) * 0.8
            ax = self.plt.subplot(111)
            ax.bar(context.active_object['livires']['valbins'], context.active_object['livires']['areabins'], width, color="blue")

        except Exception as e:
            print(e)

class dhscatter():
    def __init__(self, context, width, height):
        self.plt = plt
#        self.fig = self.plt.figure()
        self.oname = context.active_object.name if context.active_object else ''
        self.spos = [int(0.15 * width), int(0.175 * height)]
        self.epos = [int(0.9 * width), int(0.925 * height)]
        self.gspos = [int(0.15 * width), int(0.65 * height)]
        self.gepos = [int(0.75 * width), int(0.9 * height)]
        self.pos = [0.3 * width, 0.9 * height]
        self.gpos = (self.pos[0] + 0.2 * width, self.pos[1] - 0.2 * height)        
        self.hl = (1, 1, 1, 1)
        self.expand = 0
        self.image = bpy.data.images.load('/home/ryan/.config/blender/2.77/scripts/addons/vi-suite04/images/stats.png') 
        self.image.user_clear()
        self.scatterloc = os.path.join(context.scene['viparams']['newdir'], 'images', 'scatter.png') 
        self.vicon = context.scene['viparams']['visimcontext']
        self.unit = context.scene.li_disp_da
        resobs = [o for o in context.scene.objects if self.vicon in resdict and o.get(resdict[self.vicon]) and o.licalc]
        res = [o[resdict[self.vicon]][restypedict[context.scene.li_disp_da]] for o in resobs]
        res = nadd(*res)/len(res) if len(res) > 1 else res
        self.resonames = [o.name for o in resobs]
        self.scattergraph(context, resobs[0][resdict[self.vicon]][daydict[resdict[self.vicon]]], resobs[0][resdict[self.vicon]][hourdict[resdict[self.vicon]]], res, 'All ' + titledict[context.scene.li_disp_da], 'Day', 'Hour', context.scene['liparams']['unit'])            
        self.savegraph(context.scene)
        
        if 'scatter.png' not in [i.name for i in bpy.data.images]:
            self.gimage = bpy.data.images.load(self.scatterloc)
        elif 'scatter.png' in [i.name for i in bpy.data.images]:
            bpy.data.images['scatter.png'].reload()
            self.gimage = bpy.data.images['scatter.png']

        self.gimage.user_clear()
        self.drawclosed(context, width, height)
            
    def scattergraph(self, context, x, y, z, tit, xlab, ylab, zlab):
        try:
            self.plt.close()
            col = context.scene.vi_leg_col
            x = [x[0] - 0.5] + [xval + 0.5 for xval in x] 
            y = [y[0] - 0.5] + [yval + 0.5 for yval in y]
            print(len(x), len(y), z.shape)
            self.plt.title(tit, size = 20)
            self.plt.xlabel(xlab, size = 18)
            self.plt.ylabel(ylab, size = 18)
            self.plt.pcolor(x, y, z, cmap=col)#, norm=plt.matplotlib.colors.LogNorm())#, edgecolors='b', linewidths=1, vmin = 0, vmax = 4000)
            self.plt.colorbar().set_label(label=zlab,size=18)
            self.plt.axis([min(x),max(x),min(y),max(y)], size = 16)
#            self.plt.rcParams["figure.figsize"] = [16, 8]
            self.plt.tight_layout()

        except Exception as e:
            print(e)

    def savegraph(self, scene):
        self.plt.savefig(os.path.join(scene['viparams']['newdir'], 'images', 'scatter.png'))
        
    def draw(self, context, width, height):
        if self.pos[1] > height:
            self.pos[1] = height
        self.spos = (int(self.pos[0] - (width * 0.025)), int(self.pos[1] - (height * 0.025)))
        self.epos = (int(self.pos[0] + (width * 0.025)), int(self.pos[1] + (height * 0.025)))
        if self.expand == 0:
            self.drawclosed(context, width, height)
        if self.expand == 1:
            self.drawopen(context, width, height)
        
    def drawclosed(self, context, width, height):
        font_id = 0
        blf.enable(0, 4)
        blf.enable(0, 8)
        blf.shadow(font_id, 5, 0.5, 0.5, 0.5, 1)
        blf.size(font_id, 56, int(height * 0.05))
        drawpoly(self.spos[0], self.spos[1], self.epos[0], self.epos[1], *self.hl)        
        drawloop(self.spos[0], self.spos[1], self.epos[0], self.epos[1])
        bgl.glEnable(bgl.GL_BLEND)
        self.image.gl_load(bgl.GL_NEAREST, bgl.GL_NEAREST)
        bgl.glBindTexture(bgl.GL_TEXTURE_2D, self.image.bindcode[0])
        bgl.glTexParameteri(bgl.GL_TEXTURE_2D,
                                bgl.GL_TEXTURE_MAG_FILTER, bgl.GL_LINEAR)
        bgl.glTexParameteri(bgl.GL_TEXTURE_2D,
                                bgl.GL_TEXTURE_MIN_FILTER, bgl.GL_LINEAR)
        bgl.glEnable(bgl.GL_TEXTURE_2D)
        bgl.glColor4f(1, 1, 1, 1)
        bgl.glBegin(bgl.GL_QUADS)
        bgl.glTexCoord2i(0, 0)
        bgl.glVertex2f(self.spos[0] + 5, self.spos[1] + 5)
        bgl.glTexCoord2i(1, 0)
        bgl.glVertex2f(self.epos[0] - 5, self.spos[1] + 5)
        bgl.glTexCoord2i(1, 1)
        bgl.glVertex2f(self.epos[0] - 5, self.epos[1] - 5)
        bgl.glTexCoord2i(0, 1)
        bgl.glVertex2f(self.spos[0] + 5, self.epos[1] - 5)
        bgl.glEnd()
        bgl.glDisable(bgl.GL_TEXTURE_2D)
        bgl.glDisable(bgl.GL_BLEND)
        bgl.glFlush()
        
    def drawopen(self, context, width, height):
        self.drawclosed(context, width, height)
        self.gimage.reload()
        self.gspos = [self.spos[0], int(self.spos[1] - 0.4 * height)]
        self.gepos = [int(self.spos[0] + 0.6 * width), self.spos[1]]
        drawpoly(self.gspos[0], self.gspos[1], self.gepos[0], self.gepos[1], *self.hl)        
        drawloop(self.gspos[0], self.gspos[1], self.gepos[0], self.gepos[1])
        
        bgl.glEnable(bgl.GL_BLEND)
        self.gimage.gl_load(bgl.GL_NEAREST, bgl.GL_NEAREST)
        bgl.glBindTexture(bgl.GL_TEXTURE_2D, self.gimage.bindcode[0])
        bgl.glTexParameteri(bgl.GL_TEXTURE_2D,
                                bgl.GL_TEXTURE_MAG_FILTER, bgl.GL_LINEAR)
        bgl.glTexParameteri(bgl.GL_TEXTURE_2D,
                                bgl.GL_TEXTURE_MIN_FILTER, bgl.GL_LINEAR)
        bgl.glEnable(bgl.GL_TEXTURE_2D)
        bgl.glColor4f(1, 1, 1, 1)
        bgl.glBegin(bgl.GL_QUADS)
        bgl.glTexCoord2i(0, 0)
        bgl.glVertex2f(self.gspos[0] + 5, self.gspos[1] + 5)
        bgl.glTexCoord2i(1, 0)
        bgl.glVertex2f(self.gepos[0] - 5, self.gspos[1] + 5)
        bgl.glTexCoord2i(1, 1)
        bgl.glVertex2f(self.gepos[0] - 5, self.gepos[1] - 5)
        bgl.glTexCoord2i(0, 1)
        bgl.glVertex2f(self.gspos[0] + 5, self.gepos[1] - 5)
        bgl.glEnd()
        bgl.glDisable(bgl.GL_TEXTURE_2D)
        bgl.glFlush()
    
class table():
    def __init__(self, context, width, height):
        self.pos = (0.4 * width, 0.9 * height)        
        self.image = bpy.data.images.load('/home/ryan/.config/blender/2.77/scripts/addons/vi-suite04/images/table.png')        
        self.image.user_clear()
        self.hl = (1, 1, 1, 1)
        self.drawclosed(context, width, height)
        self.expand = 0
#        self.rcarray = rcarray
        
    def draw(self, context, width, height, rcarray): 
        if self.pos[1] > height:
            self.pos[1] = height
        self.spos = (int(self.pos[0] - (width * 0.025)), int(self.pos[1] - (height * 0.025)))
        self.epos = (int(self.pos[0] + (width * 0.025)), int(self.pos[1] + (height * 0.025)))        
        if self.expand == 0:
            self.drawclosed(context, width, height)
        if self.expand == 1:
            self.drawopen(context, width, height, rcarray)
        
    def drawclosed(self, context, width, height):
        self.spos = (int(self.pos[0] - (width * 0.025)), int(self.pos[1] - (height * 0.025)))
        self.epos = (int(self.pos[0] + (width * 0.025)), int(self.pos[1] + (height * 0.025)))
        drawpoly(self.spos[0], self.spos[1], self.epos[0], self.epos[1], *self.hl)        
        drawloop(self.spos[0], self.spos[1], self.epos[0], self.epos[1])
        bgl.glEnable(bgl.GL_BLEND)
        self.image.gl_load(bgl.GL_NEAREST, bgl.GL_NEAREST)
        bgl.glBindTexture(bgl.GL_TEXTURE_2D, self.image.bindcode[0])
        bgl.glTexParameteri(bgl.GL_TEXTURE_2D,
                                bgl.GL_TEXTURE_MAG_FILTER, bgl.GL_LINEAR)
        bgl.glTexParameteri(bgl.GL_TEXTURE_2D,
                                bgl.GL_TEXTURE_MIN_FILTER, bgl.GL_LINEAR)
        bgl.glEnable(bgl.GL_TEXTURE_2D)
        bgl.glColor4f(1, 1, 1, 1)
        bgl.glBegin(bgl.GL_QUADS)
        bgl.glTexCoord2i(0, 0)
        bgl.glVertex2f(self.spos[0] + 5, self.spos[1] + 5)
        bgl.glTexCoord2i(1, 0)
        bgl.glVertex2f(self.epos[0] - 5, self.spos[1] + 5)
        bgl.glTexCoord2i(1, 1)
        bgl.glVertex2f(self.epos[0] - 5, self.epos[1] - 5)
        bgl.glTexCoord2i(0, 1)
        bgl.glVertex2f(self.spos[0] + 5, self.epos[1] - 5)
        bgl.glEnd()
        bgl.glDisable(bgl.GL_TEXTURE_2D)
        bgl.glFlush()
        
    def drawopen(self, context, width, height, rcarray):
        self.drawclosed(context, width, height) 
        font_id = 0
        blf.enable(0, 4)
        blf.enable(0, 8)
        blf.shadow(font_id, 5, 0.9, 0.9, 0.9, 1)
        blf.size(font_id, 42, int(height * 0.05))
        rcshape = rcarray.shape
        [rowno, colno] = rcarray.shape
        colpos = [0]
        colwidths = [int(max([blf.dimensions(font_id, '{}'.format(e))[0] for e in entry]) + 0.01 * width) for entry in rcarray.T]
        for cw in colwidths:
            colpos.append(cw + colpos[-1])

        rowheight = max([int(max([blf.dimensions(font_id, '{}'.format(e))[1] + 0.005 * width for e in entry]) + 0.005 * width) for entry in rcarray.T])
        self.gspos = [self.spos[0], int(self.spos[1] - rowno * rowheight) - 10]
        self.gepos = [int(self.spos[0] + sum(colwidths) + 10), self.spos[1]]
        drawpoly(self.gspos[0], self.gspos[1], self.gepos[0], self.gepos[1], *self.hl)        
        drawloop(self.gspos[0], self.gspos[1], self.gepos[0], self.gepos[1])        
        bgl.glEnable(bgl.GL_BLEND)
        
        for r in range(rcshape[0]):
            for c in range(rcshape[1]):
                blf.position(font_id, self.gspos[0] + 5 + colpos[c] + colwidths[c] * 0.5 - int(blf.dimensions(font_id, '{}'.format(rcarray[r][c]))[0] * 0.5), self.gepos[1] - 5 - int(rowheight * (r + 0.5)) - int(blf.dimensions(font_id, '{}'.format(rcarray[1][1]))[1] * 0.5), 0)
                drawloop(self.gspos[0] + colpos[c] + 5, self.gspos[1] + int(r * rowheight) + 5, self.gspos[0] + colpos[c + 1] + 5, self.gspos[1] + int((r + 1) * rowheight) + 5)                
                blf.draw(font_id, '{}'.format(rcarray[r][c]))
        blf.disable(0, 8)
        blf.disable(0, 4)
        
        bgl.glEnd()
        bgl.glFlush()
        
class bsdf2():
    def __init__(self, context, width, height):
        self.plt = plt
        self.pos = [0.1 * width, 0.9 * height] 
        self.spos = [int(self.pos[0] - 0.025 * width), int(self.pos[1] - 0.025 * height)]
        self.epos = [int(self.pos[0] + 0.025 * width), int(self.pos[1] + 0.025 * height)]
        self.xdiff, self.ydiff = 801, 401
        self.gspos = [self.spos[0], self.spos[1] - self.ydiff]
        self.gepos = [self.spos[0] + self.xdiff, self.spos[1]]
        self.gpos = (self.pos[0] + 0.2 * width, self.pos[1] - 0.2 * height)
        self.image = bpy.data.images.load(os.path.join(sys.path[0], 'images/bsdf.png'))       
        self.image.user_clear()
        self.bsdfloc = os.path.join(context.scene['viparams']['newdir'], 'images', 'bsdfplot.png') 

        if 'bsdfplot.png' not in [i.name for i in bpy.data.images]:
            self.gimage = bpy.data.images.load(self.bsdfloc)
        else:
            bpy.data.images['bsdfplot.png'].reload()
            self.gimage = bpy.data.images['bsdfplot.png']

        self.hl = (1, 1, 1, 1)
        self.col = coldict[context.scene.vi_leg_col]
        self.patch_select = 0
        self.type_select = 0
        self.patch_hl = 0
        self.scale_select = 'Log'
        self.resize = 0
        self.buttons = {}
        self.leg_max, self.leg_min = context.scene.bsdf_leg_max, context.scene.bsdf_leg_min 
        self.num_disp = 0
#        self.vicon = context.scene['viparams']['visimcontext']
#        self.unit = context.scene.li_disp_da
        self.mat = context.object.active_material
        self.update()
#        self.plot(context.scene)
#        self.save(context.scene)
        self.drawclosed(context, width, height)
        self.expand = 0

    def update(self):
        bsdf = minidom.parseString(self.mat['bsdf']['xml'])
        coltype = [path.firstChild.data for path in bsdf.getElementsByTagName('ColumnAngleBasis')]
        rowtype = [path.firstChild.data for path in bsdf.getElementsByTagName('RowAngleBasis')]
        self.radtype = [path.firstChild.data for path in bsdf.getElementsByTagName('Wavelength')]
        self.rad_select = self.radtype[0]
        self.dattype = [path.firstChild.data for path in bsdf.getElementsByTagName('WavelengthDataDirection')]
        self.type_select = self.dattype[0].split()[0]
        self.dir_select = self.dattype[0].split()[1]
        lthetas = [path.firstChild.data for path in bsdf.getElementsByTagName('LowerTheta')]
        self.uthetas = [float(path.firstChild.data) for path in bsdf.getElementsByTagName('UpperTheta')]
        self.phis = [int(path.firstChild.data) for path in bsdf.getElementsByTagName('nPhis')]
        self.scatdat = [array([float(nv) for nv in path.firstChild.data.strip('\t').strip('\n').strip(',').split(' ') if nv]) for path in bsdf.getElementsByTagName('ScatteringData')]
            
    def draw(self, context, width, height):  
        if self.pos[1] > height:
            self.pos[1] = height
        self.spos = (int(self.pos[0] - (width * 0.025)), int(self.pos[1] - (height * 0.025)))
        self.epos = (int(self.pos[0] + (width * 0.025)), int(self.pos[1] + (height * 0.025)))
        if self.expand == 0:
            self.drawclosed(context, width, height)
        if self.expand == 1:
            self.drawopen(context, width, height)
            
    def drawclosed(self, context, width, height):
        font_id = 0
        blf.enable(0, 4)
        blf.enable(0, 8)
        blf.shadow(font_id, 5, 0.5, 0.5, 0.5, 1)
        blf.size(font_id, 56, int(height * 0.05))
        drawpoly(self.spos[0], self.spos[1], self.epos[0], self.epos[1], *self.hl)        
        drawloop(self.spos[0], self.spos[1], self.epos[0], self.epos[1])
        bgl.glEnable(bgl.GL_BLEND)
        self.image.gl_load(bgl.GL_NEAREST, bgl.GL_NEAREST)
        bgl.glBindTexture(bgl.GL_TEXTURE_2D, self.image.bindcode[0])
        bgl.glTexParameteri(bgl.GL_TEXTURE_2D,
                                bgl.GL_TEXTURE_MAG_FILTER, bgl.GL_LINEAR)
        bgl.glTexParameteri(bgl.GL_TEXTURE_2D,
                                bgl.GL_TEXTURE_MIN_FILTER, bgl.GL_LINEAR)
        bgl.glEnable(bgl.GL_TEXTURE_2D)
        bgl.glColor4f(1, 1, 1, 1)
        bgl.glBegin(bgl.GL_QUADS)
        bgl.glTexCoord2i(0, 0)
        bgl.glVertex2f(self.spos[0] + 5, self.spos[1] + 5)
        bgl.glTexCoord2i(1, 0)
        bgl.glVertex2f(self.epos[0] - 5, self.spos[1] + 5)
        bgl.glTexCoord2i(1, 1)
        bgl.glVertex2f(self.epos[0] - 5, self.epos[1] - 5)
        bgl.glTexCoord2i(0, 1)
        bgl.glVertex2f(self.spos[0] + 5, self.epos[1] - 5)
        bgl.glEnd()
        bgl.glDisable(bgl.GL_TEXTURE_2D)
        bgl.glDisable(bgl.GL_BLEND)
        bgl.glFlush()
        
    def drawopen(self, context, width, height):
        bgl.glEnable(bgl.GL_BLEND)
        bgl.glEnable(bgl.GL_DEPTH_TEST)
        self.drawclosed(context, width, height)
        self.gimage.reload()
        self.xdiff = self.gepos[0] - self.gspos[0]
        self.ydiff = self.gepos[1] - self.gspos[1]
        
        if not self.resize:
            self.gspos = [self.spos[0], self.spos[1] - self.ydiff]
            self.gepos = [self.spos[0] + self.xdiff, self.spos[1]]            
        else:
            self.gspos = [self.spos[0], self.gspos[1]]
            self.gepos = [self.gepos[0], self.spos[1]]

        self.centre = (self.gspos[0] + 0.225 * self.xdiff, self.gspos[1] + 0.425 * self.ydiff)
        drawpoly(self.gspos[0], self.gspos[1], self.gepos[0], self.gepos[1], 1, 1, 1, 1)        
        drawloop(self.gspos[0], self.gspos[1], self.gepos[0], self.gepos[1])
        self.pw, self.ph = 0.175 * self.xdiff, 0.35 * self.ydiff
        self.radii = array([0.125, 0.25, 0.375, 0.5, 0.625, 0.75, 0.875, 1, 1.125])
        cent = [self.gspos[0] + 0.02 * self.xdiff, self.gepos[1] - 0.03 * self.ydiff]
        buttons = {}
        drawcircle(self.centre, self.radii[-1] + 0.01, 360, 1, (0.95, 0.95, 0.95, 1), self.pw, self.ph, 0.04, 2)
        
        for rt in set(self.radtype):                
            drawsquare(cent, 0.02 * self.xdiff, 0.03 * self.ydiff, 0)
            if self.rad_select == rt:
                drawsquare(cent, 0.015 * self.xdiff, 0.02 * self.ydiff, (0.5, 0.5, 0.5, 1))
            blf.position(0, cent[0] + 0.015 * self.xdiff, cent[1] - 0.015 * self.ydiff, 0)
            blf.size(0, 56, int(0.025 * self.xdiff))
            blf.draw(0, rt)
            buttons[rt] = cent[:]
            cent[0] += 0.15 * self.xdiff                 

        cent[1] = cent[1] - 0.05 * self.ydiff
        cent[0] = self.gspos[0] + 0.02 * self.xdiff

        for dt in set([dt.split()[1] for dt in self.dattype]):
            drawsquare(cent, 0.02 * self.xdiff, 0.03 * self.ydiff, 0) 
            if self.dir_select == dt:
                drawsquare(cent, 0.015 * self.xdiff, 0.02 * self.ydiff, (0.5, 0.5, 0.5, 1))
            blf.position(0, cent[0] + 0.015 * self.xdiff, cent[1] - 0.015 * self.ydiff, 0)
            blf.size(0, 56, int(0.025 * self.xdiff))
            blf.draw(0, dt)
            buttons[dt] = cent[:]
            cent[0] += 0.15 * self.xdiff
            
        cent[1] -= 0.05 * self.ydiff
        cent[0] = self.gspos[0] + 0.02 * self.xdiff

        for dt in set([dt.split()[0] for dt in self.dattype]):
            drawsquare(cent, 0.02 * self.xdiff, 0.03 * self.ydiff, 0) 
            if self.type_select == dt:
                drawsquare(cent, 0.015 * self.xdiff, 0.02 * self.ydiff, (0.5, 0.5, 0.5, 1))
            blf.position(0, cent[0] + 0.015 * self.xdiff, cent[1] - 0.015 * self.ydiff, 0)
            blf.size(0, 56, int(0.025 * self.xdiff))
            blf.draw(0, dt)
            buttons[dt] = cent[:]
            cent[0] += 0.15 * self.xdiff
        cent = [self.gspos[0] + 0.55 * self.xdiff, self.gspos[1] + 0.04 * self.ydiff]
        
        for pt in ('Log', 'Linear'):            
            drawsquare(cent, 0.02 * self.xdiff, 0.03 * self.ydiff, 0) 
            if self.scale_select == pt:
                drawsquare(cent, 0.015 * self.xdiff, 0.02 * self.ydiff, (0.5, 0.5, 0.5, 1))
            blf.position(0, cent[0] + 0.015 * self.xdiff, cent[1] - 0.015 * self.ydiff, 0.01)
            blf.size(0, 56, int(0.025 * self.xdiff))
            blf.draw(0, pt)
            buttons[pt] = cent[:]
            cent[0] += 0.25 * self.xdiff
        
        for rdi, raddat in enumerate(['{0[0]} {0[1]}'.format(z) for z in zip(self.radtype, self.dattype)]):
            if raddat == '{} {} {}'.format(self.rad_select, self.type_select, self.dir_select):
                self.scat_select = rdi
                break 
        self.buttons = buttons
        selectdat = self.scatdat[self.scat_select].reshape(145, 145)# if self.scale_select == 'Linear' else nlog10((self.scatdat[self.scat_select] + 1).reshape(145, 145)) 
        sa = repeat(kfsa, self.phis)
        act = repeat(kfact, self.phis)
        patchdat = selectdat[self.patch_select] * act * sa * 100
        patch = 0
        centre2 = (self.centre[0] + 0.5 * self.xdiff, self.centre[1])
        cmap = mcm.get_cmap(self.col)
        
        for phii, phi in enumerate(self.phis):
            for w in range(phi):
                if self.patch_select == patch:
                    z, lw, col = 0.06, 5, (1, 0, 0, 1) 
                elif self.patch_hl == patch:
                    z, lw, col = 0.06, 5, (1, 1, 0, 1)
                else:
                    z, lw, col = 0.05, 1, 0
    
#                for centre in (self.centre, centre2)
                if phi == 1:
                    drawcircle(self.centre, self.radii[phii], 360, 0, col, self.pw, self.ph, z, lw)
                elif phi > 1:
                    drawwedge(self.centre, (int(360*w/phi) - int(180/phi) - 90, int(360*(w + 1)/phi) - int(180/phi) - 90), (self.radii[phii] - 0.125, self.radii[phii]), col, self.pw, self.ph)
                    drawcolwedge(centre2, (int(360*w/phi) - int(180/phi) - 90, int(360*(w + 1)/phi) - int(180/phi) - 90), (self.radii[phii] - 0.125, self.radii[phii]), cmap(patchdat[patch]/max(patchdat)), self.pw, self.ph)
                    
                patch += 1

        
        


class bsdf():
    def __init__(self, context, width, height):
        self.plt = plt
        self.pos = [0.1 * width, 0.9 * height] 
        self.spos = [int(self.pos[0] - 0.025 * width), int(self.pos[1] - 0.025 * height)]
        self.epos = [int(self.pos[0] + 0.025 * width), int(self.pos[1] + 0.025 * height)]
        self.xdiff, self.ydiff = 801, 401
        self.gspos = [self.spos[0], self.spos[1] - self.ydiff]
        self.gepos = [self.spos[0] + self.xdiff, self.spos[1]]
        self.gpos = (self.pos[0] + 0.2 * width, self.pos[1] - 0.2 * height)
        self.image = bpy.data.images.load('/home/ryan/.config/blender/2.77/scripts/addons/vi-suite04/images/bsdf.png')        
        self.image.user_clear()
        self.bsdfloc = os.path.join(context.scene['viparams']['newdir'], 'images', 'bsdfplot.png') 

        if 'bsdfplot.png' not in [i.name for i in bpy.data.images]:
            self.gimage = bpy.data.images.load(self.bsdfloc)
        else:
            bpy.data.images['bsdfplot.png'].reload()
            self.gimage = bpy.data.images['bsdfplot.png']

        self.hl = (1, 1, 1, 1)
        self.col = coldict[context.scene.vi_leg_col]
        self.patch_select = 0
        self.type_select = 0
        self.patch_hl = 0
        self.scale_select = 'Log'
        self.resize = 0
        self.buttons = {}
        self.leg_max, self.leg_min = context.scene.bsdf_leg_max, context.scene.bsdf_leg_min 
        self.num_disp = 0
#        self.vicon = context.scene['viparams']['visimcontext']
#        self.unit = context.scene.li_disp_da
        self.mat = context.object.active_material
        self.update()
        self.plot(context.scene)
        self.save(context.scene)
        self.drawclosed(context, width, height)
        self.expand = 0
        
    def draw(self, context, width, height):  
        if self.pos[1] > height:
            self.pos[1] = height
        self.spos = (int(self.pos[0] - (width * 0.025)), int(self.pos[1] - (height * 0.025)))
        self.epos = (int(self.pos[0] + (width * 0.025)), int(self.pos[1] + (height * 0.025)))
        if self.expand == 0:
            self.drawclosed(context, width, height)
        if self.expand == 1:
            self.drawopen(context, width, height)
            
    def drawclosed(self, context, width, height):
        font_id = 0
        blf.enable(0, 4)
        blf.enable(0, 8)
        blf.shadow(font_id, 5, 0.5, 0.5, 0.5, 1)
        blf.size(font_id, 56, int(height * 0.05))
        drawpoly(self.spos[0], self.spos[1], self.epos[0], self.epos[1], *self.hl)        
        drawloop(self.spos[0], self.spos[1], self.epos[0], self.epos[1])
        bgl.glEnable(bgl.GL_BLEND)
        self.image.gl_load(bgl.GL_NEAREST, bgl.GL_NEAREST)
        bgl.glBindTexture(bgl.GL_TEXTURE_2D, self.image.bindcode[0])
        bgl.glTexParameteri(bgl.GL_TEXTURE_2D,
                                bgl.GL_TEXTURE_MAG_FILTER, bgl.GL_LINEAR)
        bgl.glTexParameteri(bgl.GL_TEXTURE_2D,
                                bgl.GL_TEXTURE_MIN_FILTER, bgl.GL_LINEAR)
        bgl.glEnable(bgl.GL_TEXTURE_2D)
        bgl.glColor4f(1, 1, 1, 1)
        bgl.glBegin(bgl.GL_QUADS)
        bgl.glTexCoord2i(0, 0)
        bgl.glVertex2f(self.spos[0] + 5, self.spos[1] + 5)
        bgl.glTexCoord2i(1, 0)
        bgl.glVertex2f(self.epos[0] - 5, self.spos[1] + 5)
        bgl.glTexCoord2i(1, 1)
        bgl.glVertex2f(self.epos[0] - 5, self.epos[1] - 5)
        bgl.glTexCoord2i(0, 1)
        bgl.glVertex2f(self.spos[0] + 5, self.epos[1] - 5)
        bgl.glEnd()
        bgl.glDisable(bgl.GL_TEXTURE_2D)
        bgl.glDisable(bgl.GL_BLEND)
        bgl.glFlush()
        
    def drawopen(self, context, width, height):
        bgl.glEnable(bgl.GL_BLEND)
        bgl.glEnable(bgl.GL_DEPTH_TEST)
        self.drawclosed(context, width, height)
        self.gimage.reload()
        self.xdiff = self.gepos[0] - self.gspos[0]
        self.ydiff = self.gepos[1] - self.gspos[1]
        
        if not self.resize:
            self.gspos = [self.spos[0], self.spos[1] - self.ydiff]
            self.gepos = [self.spos[0] + self.xdiff, self.spos[1]]            
        else:
            self.gspos = [self.spos[0], self.gspos[1]]
            self.gepos = [self.gepos[0], self.spos[1]]

        self.centre = (self.gspos[0] + 0.225 * self.xdiff, self.gspos[1] + 0.425 * self.ydiff)
        drawpoly(self.gspos[0], self.gspos[1], self.gepos[0], self.gepos[1], 1, 1, 1, 1)        
        drawloop(self.gspos[0], self.gspos[1], self.gepos[0], self.gepos[1])
        self.pw, self.ph = 0.175 * self.xdiff, 0.35 * self.ydiff
        self.radii = array([0.125, 0.25, 0.375, 0.5, 0.625, 0.75, 0.875, 1, 1.125])
        cent = [self.gspos[0] + 0.02 * self.xdiff, self.gepos[1] - 0.03 * self.ydiff]
        buttons = {}
        drawcircle(self.centre, self.radii[-1] + 0.01, 360, 1, (0.95, 0.95, 0.95, 1), self.pw, self.ph, 0.04, 2)
        
        for rt in set(self.radtype):                
            drawsquare(cent, 0.02 * self.xdiff, 0.03 * self.ydiff, 0)
            if self.rad_select == rt:
                drawsquare(cent, 0.015 * self.xdiff, 0.02 * self.ydiff, (0.5, 0.5, 0.5, 1))
            blf.position(0, cent[0] + 0.015 * self.xdiff, cent[1] - 0.015 * self.ydiff, 0)
            blf.size(0, 56, int(0.025 * self.xdiff))
            blf.draw(0, rt)
            buttons[rt] = cent[:]
            cent[0] += 0.15 * self.xdiff                 

        cent[1] = cent[1] - 0.05 * self.ydiff
        cent[0] = self.gspos[0] + 0.02 * self.xdiff

        for dt in set([dt.split()[1] for dt in self.dattype]):
            drawsquare(cent, 0.02 * self.xdiff, 0.03 * self.ydiff, 0) 
            if self.dir_select == dt:
                drawsquare(cent, 0.015 * self.xdiff, 0.02 * self.ydiff, (0.5, 0.5, 0.5, 1))
            blf.position(0, cent[0] + 0.015 * self.xdiff, cent[1] - 0.015 * self.ydiff, 0)
            blf.size(0, 56, int(0.025 * self.xdiff))
            blf.draw(0, dt)
            buttons[dt] = cent[:]
            cent[0] += 0.15 * self.xdiff
            
        cent[1] -= 0.05 * self.ydiff
        cent[0] = self.gspos[0] + 0.02 * self.xdiff

        for dt in set([dt.split()[0] for dt in self.dattype]):
            drawsquare(cent, 0.02 * self.xdiff, 0.03 * self.ydiff, 0) 
            if self.type_select == dt:
                drawsquare(cent, 0.015 * self.xdiff, 0.02 * self.ydiff, (0.5, 0.5, 0.5, 1))
            blf.position(0, cent[0] + 0.015 * self.xdiff, cent[1] - 0.015 * self.ydiff, 0)
            blf.size(0, 56, int(0.025 * self.xdiff))
            blf.draw(0, dt)
            buttons[dt] = cent[:]
            cent[0] += 0.15 * self.xdiff
        cent = [self.gspos[0] + 0.55 * self.xdiff, self.gspos[1] + 0.04 * self.ydiff]
        
        for pt in ('Log', 'Linear'):            
            drawsquare(cent, 0.02 * self.xdiff, 0.03 * self.ydiff, 0) 
            if self.scale_select == pt:
                drawsquare(cent, 0.015 * self.xdiff, 0.02 * self.ydiff, (0.5, 0.5, 0.5, 1))
            blf.position(0, cent[0] + 0.015 * self.xdiff, cent[1] - 0.015 * self.ydiff, 0.01)
            blf.size(0, 56, int(0.025 * self.xdiff))
            blf.draw(0, pt)
            buttons[pt] = cent[:]
            cent[0] += 0.25 * self.xdiff
            
        self.buttons = buttons
        patch = 0
        for phii, phi in enumerate(self.phis):
            for w in range(phi):
                if self.patch_select == patch:
                    z, lw, col = 0.06, 5, (1, 0, 0, 1) 
                elif self.patch_hl == patch:
                    z, lw, col = 0.06, 5, (1, 1, 0, 1)
                else:
                    z, lw, col = 0.05, 1, 0
    
                if phi == 1:
                    drawcircle(self.centre, self.radii[phii], 360, 0, col, self.pw, self.ph, z, lw)
                elif phi > 1:
                    drawwedge(self.centre, (int(360*w/phi) - int(180/phi) - 90, int(360*(w + 1)/phi) - int(180/phi) - 90), (self.radii[phii] - 0.125, self.radii[phii]), col, self.pw, self.ph)
                    
                patch += 1
        
        self.gimage.gl_load(bgl.GL_NEAREST, bgl.GL_NEAREST)
        bgl.glBindTexture(bgl.GL_TEXTURE_2D, self.gimage.bindcode[0])
        bgl.glTexParameteri(bgl.GL_TEXTURE_2D, bgl.GL_TEXTURE_MAG_FILTER, bgl.GL_LINEAR)
        bgl.glTexParameteri(bgl.GL_TEXTURE_2D, bgl.GL_TEXTURE_MIN_FILTER, bgl.GL_LINEAR)
        bgl.glEnable(bgl.GL_TEXTURE_2D)
        bgl.glColor4f(1, 1, 1, 1)
        bgl.glBegin(bgl.GL_QUADS)
        bgl.glTexCoord2i(0, 0)
        bgl.glVertex2f(self.gspos[0] + 0.45 * self.xdiff, self.gspos[1] + 5)
        bgl.glTexCoord2i(1, 0)
        bgl.glVertex2f(self.gepos[0] - 5, self.gspos[1] + 5)
        bgl.glTexCoord2i(1, 1)
        bgl.glVertex2f(self.gepos[0] - 5, self.gepos[1] - 5)
        bgl.glTexCoord2i(0, 1)
        bgl.glVertex2f(self.gspos[0] + 0.45 * self.xdiff, self.gepos[1] - 5)
        bgl.glLineWidth(2)
        bgl.glEnd()
        bgl.glDisable(bgl.GL_TEXTURE_2D)
        bgl.glDisable(bgl.GL_DEPTH_TEST)
        bgl.glDisable(bgl.GL_BLEND)
        bgl.glFlush()
        
    def update(self):
        bsdf = minidom.parseString(self.mat['bsdf']['xml'])
        coltype = [path.firstChild.data for path in bsdf.getElementsByTagName('ColumnAngleBasis')]
        rowtype = [path.firstChild.data for path in bsdf.getElementsByTagName('RowAngleBasis')]
        self.radtype = [path.firstChild.data for path in bsdf.getElementsByTagName('Wavelength')]
        self.rad_select = self.radtype[0]
        self.dattype = [path.firstChild.data for path in bsdf.getElementsByTagName('WavelengthDataDirection')]
        self.type_select = self.dattype[0].split()[0]
        self.dir_select = self.dattype[0].split()[1]
        lthetas = [path.firstChild.data for path in bsdf.getElementsByTagName('LowerTheta')]
        self.uthetas = [float(path.firstChild.data) for path in bsdf.getElementsByTagName('UpperTheta')]
        self.phis = [int(path.firstChild.data) for path in bsdf.getElementsByTagName('nPhis')]
        self.scatdat = [array([float(nv) for nv in path.firstChild.data.strip('\t').strip('\n').strip(',').split(' ') if nv]) for path in bsdf.getElementsByTagName('ScatteringData')]
            
    def plot(self, scene):
        self.plt.clf()
        self.plt.close()
        self.fig = self.plt.figure(figsize=(7.5, 7.5), dpi = 100)
        ax = self.plt.subplot(111, projection = 'polar')
        ax.bar(0, 0)
        self.plt.title('{} {} {}'.format(self.dir_select, self.rad_select, self.type_select), size = 19, y = 1.025)
        ax.axis([0, 2 * math.pi, 0, 1])
        ax.spines['polar'].set_visible(False)
        ax.xaxis.set_ticks([])
        ax.yaxis.set_ticks([])
        
        for rdi, raddat in enumerate(['{0[0]} {0[1]}'.format(z) for z in zip(self.radtype, self.dattype)]):
            if raddat == '{} {} {}'.format(self.rad_select, self.type_select, self.dir_select):
                self.scat_select = rdi
                break 

        selectdat = self.scatdat[self.scat_select].reshape(145, 145)# if self.scale_select == 'Linear' else nlog10((self.scatdat[self.scat_select] + 1).reshape(145, 145)) 
        widths = [0] + [self.uthetas[w]/90 for w in range(9)]
        patches, p = [], 0
        sa = repeat(kfsa, self.phis)
        act = repeat(kfact, self.phis)
        patchdat = selectdat[self.patch_select] * act * sa * 100
                
        for ring in range(1, 10):
            angdiv = math.pi/self.phis[ring - 1]
            anglerange = range(self.phis[ring - 1], 0, -1)# if self.type_select == 'Transmission' else range(self.phis[ring - 1])
            ri = widths[ring] - widths[ring-1]

            for wedge in anglerange:
                phi1, phi2 = wedge * 2 * angdiv - angdiv, (wedge + 1) * 2 * angdiv - angdiv
                patches.append(Rectangle((phi1, widths[ring - 1]), phi2 - phi1, ri)) 
                if self.num_disp:
                    y = 0 if ring == 1 else 0.5 * (widths[ring] + widths[ring-1])
                    self.plt.text(0.5 * (phi1 + phi2), y, ('{:.1f}', '{:.0f}')[patchdat[p] >= 10].format(patchdat[p]), ha="center", va = 'center', family='sans-serif', size=10)
                p += 1
                
        pc = PatchCollection(patches, norm=mcolors.LogNorm(vmin=self.leg_min + 0.01, vmax = self.leg_max), cmap=self.col) if self.scale_select == 'Log' else PatchCollection(patches, cmap=self.col)        
        pc.set_linewidth(repeat(array([0, 0.5]), array([1, 144])))
        pc.set_array(patchdat)
        ax.add_collection(pc)
        self.plt.colorbar(pc, fraction=0.04, pad=0.02, format = '%3g').set_label(label='Percentage of incoming flux (%)', size=18)
        pc.set_clim(vmin=self.leg_min + 0.01, vmax= self.leg_max)
        self.plt.tight_layout()
                        
    def save(self, scene):
        self.plt.savefig(os.path.join(scene['viparams']['newdir'], 'images', 'bsdfplot.png'), bbox_inches='tight') 
            
def cbdm_disp(self, context):
    width, height = context.region.width, context.region.height
    self.legend.draw(context, width, height)
    self.scatter.draw(context, width, height)
    self.table.draw(context, width, height, array([["", 'Average', 'Minimum', 'Maximum'], ['DA (%)', '1', '2', '3']]))
    
def basic_disp(self, context):
    width, height = context.region.width, context.region.height
    self.legend.draw(context, width, height)
    self.bar.draw(context, width, height)
    self.table.draw(context, width, height)
    
def envi_disp(self, context):
    width, height = context.region.width, context.region.height
    self.scatter.draw(context, width, height)
    self.table.draw(context, width, height)

def bsdf2_disp(self, context):
    width, height = context.region.width, context.region.height
    self.bsdf.draw(context, width, height)
    
def bsdf_disp(self, context):
    width, height = context.region.width, context.region.height
    self.bsdf.draw(context, width, height)
#    self.table.draw(context, width, height)
def drawsquare(c, w, h, col):
#    bgl.glEnable(bgl.GL_BLEND)
#    bgl.glEnable(bgl.GL_DEPTH_TEST)
#    bgl.glEnable(bgl.GL_LINE_SMOOTH)
    vxs = (c[0] + 0.5 * w, c[0] + 0.5 * w, c[0] - 0.5 * w, c[0] - 0.5 * w)
    vys = (c[1] - 0.5 * h, c[1] + 0.5 * h, c[1] + 0.5 * h, c[1] - 0.5 * h)
#    bgl.glEnable(bgl.GL_DEPTH_TEST)
    if col:
        bgl.glColor4f(*col)
#        bgl.glLineWidth(5)
        z = 0.1
        bgl.glBegin(bgl.GL_POLYGON)
    else:        
        z = 0.05
        bgl.glLineWidth(1)
        bgl.glColor4f(0, 0, 0, 1)
        bgl.glBegin(bgl.GL_LINE_LOOP)
    for v in range(4):
        bgl.glVertex3f(vxs[v], vys[v], z)
    bgl.glLineWidth(1)
    bgl.glColor4f(0, 0, 0, 1)
#    bgl.glDisable(bgl.GL_DEPTH_TEST)
    bgl.glEnd()
    
#    bgl.glDisable(bgl.GL_TEXTURE_2D)
#    bgl.glDisable(bgl.GL_BLEND)
#    bgl.glFlush()

def drawcolwedge(c, phis, rs, col, w, h):
    bgl.glEnable(bgl.GL_BLEND)
    bgl.glEnable(bgl.GL_LINE_SMOOTH)    
    bgl.glBlendFunc(bgl.GL_SRC_ALPHA, bgl.GL_ONE_MINUS_SRC_ALPHA);
    bgl.glHint(bgl.GL_LINE_SMOOTH_HINT, bgl.GL_FASTEST)
#    z = 
    (z, lw, col) = (1/rs[1], 5, col) if col else (0.05, 1.5, [0, 0, 0, 0.25])
    bgl.glColor4f(*col)
    bgl.glLineWidth(lw)
    bgl.glBegin(bgl.GL_POLYGON)
    for p in range(phis[0], phis[1] + 1):
        bgl.glVertex3f(*radial2xy(c, rs[0], p, w, h), z)
    for p in range(phis[1], phis[0] - 1, -1):
        bgl.glVertex3f(*radial2xy(c, rs[1], p, w, h), z)
    bgl.glLineWidth(1)
    
    bgl.glEnd()
    bgl.glDisable(bgl.GL_BLEND)
            
def drawwedge(c, phis, rs, col, w, h):
    bgl.glEnable(bgl.GL_BLEND)
    bgl.glEnable(bgl.GL_LINE_SMOOTH)    
    bgl.glBlendFunc(bgl.GL_SRC_ALPHA, bgl.GL_ONE_MINUS_SRC_ALPHA);
    bgl.glHint(bgl.GL_LINE_SMOOTH_HINT, bgl.GL_FASTEST)
    (z, lw, col) = (0.1, 5, col) if col else (0.05, 1.5, [0, 0, 0, 0.25])
    bgl.glColor4f(*col)
    bgl.glLineWidth(lw)
    bgl.glBegin(bgl.GL_LINE_LOOP)
    for p in range(phis[0], phis[1] + 1):
        bgl.glVertex3f(*radial2xy(c, rs[0], p, w, h), z)
    for p in range(phis[1], phis[0] - 1, -1):
        bgl.glVertex3f(*radial2xy(c, rs[1], p, w, h), z)
    bgl.glLineWidth(1)
    
    bgl.glEnd()
    bgl.glDisable(bgl.GL_BLEND)
    
def radial2xy(c, theta, phi, w, h):
    return c[0] + theta * sin(math.pi * phi/180) * w, c[1] + theta * math.cos(math.pi * phi/180) * h
    
def xy2radial(c, pos, w, h):
    dx, dy = pos[0] - c[0], pos[1] - c[1]
    hypo = (((dx/w)**2 + (dy/h)**2)**0.5)
    at = math.atan((dy/h)/(dx/w))
    if dx == 0:
        azi = 0 if dy >= 0 else math.pi
    elif dx > 0:
        azi = math.pi * 0.5 - at
    elif dx < 0:
        azi = math.pi * 1.5 - at   
    return hypo, azi
                
def drawcircle(centre, radius, resolution, fill, col, w, h, z, lw): 
    bgl.glEnable(bgl.GL_BLEND)
    bgl.glEnable(bgl.GL_LINE_SMOOTH)
    bgl.glBlendFunc(bgl.GL_SRC_ALPHA, bgl.GL_ONE_MINUS_SRC_ALPHA)
    bgl.glHint(bgl.GL_LINE_SMOOTH_HINT, bgl.GL_NICEST)
    bgl.glLineWidth(lw)
    if not fill:
        if col:
            bgl.glColor4f(*col)
            
        bgl.glBegin(bgl.GL_LINE_LOOP)
    else:
        bgl.glColor4f(*col)
        bgl.glLineWidth(2.5)
        bgl.glBegin(bgl.GL_POLYGON)
    for p in range(0, resolution):
        bgl.glVertex3f(centre[0] + radius * math.sin(math.pi * p/180) * w, centre[1] + radius * math.cos(math.pi * p/180) * h, z)

    bgl.glEnd()
    bgl.glDisable(bgl.GL_BLEND)
    
def register():
    Scene = bpy.types.Scene
    Scene.bsdf_leg_max = bpy.props.FloatProperty(name = "", description = "Legend maximum", min = 0, max = 100, default = 100)
    Scene.bsdf_leg_min = bpy.props.FloatProperty(name = "", description = "Legend minimum", min = 0, max = 100, default = 0)

    bpy.utils.register_module(__name__)
    
def unregister():
    bpy.utils.unregister_module(__name__)