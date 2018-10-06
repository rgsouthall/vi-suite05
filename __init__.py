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

bl_info = {
    "name": "VI-Suite",
    "author": "Ryan Southall",
    "version": (0, 5, 1),
    "blender": (2, 7, 9),
    "api":"",
    "location": "Node Editor & 3D View > Properties Panel",
    "description": "Radiance/EnergyPlus exporter and results visualiser",
    "warning": "This is a beta script. Some functionality is buggy",
    "wiki_url": "",
    "tracker_url": "",
    "category": "Import-Export"}

if "bpy" in locals():
    import imp
    imp.reload(vi_node)
    imp.reload(vi_operators)
    imp.reload(vi_ui)
    imp.reload(vi_func)
    imp.reload(envi_mat)
else:
    from .vi_node import vinode_categories, envinode_categories, envimatnode_categories
    from .envi_mat import envi_materials, envi_constructions, envi_layero, envi_layer1, envi_layer2, envi_layer3, envi_layer4, envi_layerotype, envi_layer1type, envi_layer2type, envi_layer3type, envi_layer4type, envi_con_list
    from .vi_func import iprop, bprop, eprop, fprop, sprop, fvprop, sunpath1, radmat, radbsdf, retsv, cmap
    from .vi_func import rtpoints, lhcalcapply, udidacalcapply, compcalcapply, basiccalcapply, lividisplay, setscenelivivals
    from .envi_func import enunits, enpunits, enparametric, resnameunits, aresnameunits
    from .flovi_func import fvmat, ret_fvbp_menu, ret_fvbu_menu, ret_fvbnut_menu, ret_fvbnutilda_menu, ret_fvbk_menu, ret_fvbepsilon_menu, ret_fvbomega_menu, ret_fvbt_menu, ret_fvba_menu, ret_fvbprgh_menu
    from .vi_display import setcols
    from .vi_operators import *
    from .vi_ui import *

import sys, os, inspect, bpy, nodeitems_utils, bmesh, math, mathutils
from bpy.app.handlers import persistent
from numpy import array, digitize, logspace, multiply
from numpy import log10 as nlog10
from bpy.props import StringProperty, EnumProperty
from bpy.types import AddonPreferences

def return_preferences():
    return bpy.context.user_preferences.addons[__name__].preferences

def abspath(self, context):
    if self.radbin != bpy.path.abspath(self.radbin):
        self.radbin = bpy.path.abspath(self.radbin)
    if self.radlib != bpy.path.abspath(self.radlib):
        self.radlib = bpy.path.abspath(self.radlib)
    if self.epbin != bpy.path.abspath(self.epbin):
        self.epbin = bpy.path.abspath(self.epbin)
    if self.epweath != bpy.path.abspath(self.epweath):
        self.epweath = bpy.path.abspath(self.epweath)
    if self.ofbin != bpy.path.abspath(self.ofbin):
        self.ofbin = bpy.path.abspath(self.ofbin)
    if self.oflib != bpy.path.abspath(self.oflib):
        self.oflib = bpy.path.abspath(self.oflib)  
    if self.ofetc != bpy.path.abspath(self.ofetc):
        self.ofetc = bpy.path.abspath(self.ofetc)

class VIPreferences(AddonPreferences):
    bl_idname = __name__

    radbin = StringProperty(name = '', description = 'Radiance binary directory location', default = '', subtype='DIR_PATH', update=abspath)
    radlib = StringProperty(name = '', description = 'Radiance library directory location', default = '', subtype='DIR_PATH', update=abspath)
    epbin = StringProperty(name = '', description = 'EnergyPlus binary directory location', default = '', subtype='DIR_PATH', update=abspath)
    epweath = StringProperty(name = '', description = 'EnergyPlus weather directory location', default = '', subtype='DIR_PATH', update=abspath)
    ofbin = StringProperty(name = '', description = 'OpenFOAM binary directory location', default = '', subtype='DIR_PATH', update=abspath)
    oflib = StringProperty(name = '', description = 'OpenFOAM library directory location', default = '', subtype='DIR_PATH', update=abspath)
    ofetc = StringProperty(name = '', description = 'OpenFOAM letc directory location', default = '', subtype='DIR_PATH', update=abspath)
    ui_dict = {"Radiance bin directory:": 'radbin', "Radiance lib directory:": 'radlib', "EnergyPlus bin directory:": 'epbin',
               "EnergyPlus weather directory:": 'epweath', 'OpenFOAM bin directory': 'ofbin', 'OpenFOAM lib directory': 'oflib', 'OpenFOAM etc directory': 'ofetc'}

    def draw(self, context):
        layout = self.layout

        for entry in self.ui_dict:
            row = layout.row()
            row.label(text=entry)
            row.prop(self, self.ui_dict[entry])

@persistent
def update_chart_node(dummy):
    try:
        for ng in [ng for ng in bpy.data.node_groups if ng.bl_idname == 'ViN']:
            [node.update() for node in ng.nodes if node.bl_label == 'VI Chart']
    except Exception as e:
        print('Chart node update failure:', e)

@persistent
def update_dir(dummy):
    if bpy.context.scene.get('viparams'):
        fp = bpy.data.filepath
        bpy.context.scene['viparams']['newdir'] = os.path.join(os.path.dirname(fp), os.path.splitext(os.path.basename(fp))[0])

@persistent
def display_off(dummy):
    if bpy.context.scene.get('viparams') and bpy.context.scene['viparams'].get('vidisp'):

        ifdict = {'sspanel': 'ss', 'lipanel': 'li', 'enpanel': 'en', 'bsdf_panel': 'bsdf'}
        if bpy.context.scene['viparams']['vidisp'] in ifdict:
            bpy.context.scene['viparams']['vidisp'] = ifdict[bpy.context.scene['viparams']['vidisp']]
        bpy.context.scene.vi_display = 0

@persistent
def mesh_index(dummy):
    try:
        cao = bpy.context.active_object

        if cao and cao.layers[1] and cao.mode == 'EDIT':
            if not bpy.app.debug:
                bpy.app.debug = True
        elif bpy.app.debug:
            bpy.app.debug = False
    except:
        pass

@persistent
def select_nodetree(dummy):
    for space in getViEditorSpaces():
        vings = [ng for ng in bpy.data.node_groups if ng.bl_idname == 'ViN']
        if vings:
            space.node_tree = vings[0]

    for space in getEnViEditorSpaces():
        envings = [ng for ng in bpy.data.node_groups if ng.bl_idname == 'EnViN']
        if envings:
            space.node_tree = envings[0]

    for space in getEnViMaterialSpaces():
        try:
            if space.node_tree != bpy.context.active_object.active_material.envi_nodes:
                envings = [ng for ng in bpy.data.node_groups if ng.bl_idname == 'EnViMatN' and ng == bpy.context.active_object.active_material.envi_nodes]
                if envings:
                    space.node_tree = envings[0]
        except:
            pass

bpy.app.handlers.scene_update_post.append(select_nodetree)

def getViEditorSpaces():
    if bpy.context.screen:
        return [area.spaces.active for area in bpy.context.screen.areas if area and area.type == "NODE_EDITOR" and area.spaces.active.tree_type == "ViN" and not area.spaces.active.edit_tree]
    else:
        return []

def getEnViEditorSpaces():
    if bpy.context.screen:
        return [area.spaces.active for area in bpy.context.screen.areas if area and area.type == "NODE_EDITOR" and area.spaces.active.tree_type == "EnViN" and not area.spaces.active.edit_tree]
    else:
        return []

def getEnViMaterialSpaces():
    if bpy.context.screen:
        return [area.spaces.active for area in bpy.context.screen.areas if area and area.type == "NODE_EDITOR" and area.spaces.active.tree_type == "EnViMatN"]
    else:
        return []

bpy.app.handlers.scene_update_post.append(select_nodetree)
bpy.app.handlers.scene_update_post.append(mesh_index)

epversion = "8-9-0"
envi_mats, envi_cons, conlayers = envi_materials(), envi_constructions(), 5
addonpath = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
#matpath, epwpath  = addonpath+'/EPFiles/Materials/Materials.data', addonpath+'/EPFiles/Weather/'

def path_update():
    evsep = {'linux': ':', 'darwin': ':', 'win32': ';'}
    vi_prefs = bpy.context.user_preferences.addons[__name__].preferences
    epdir = vi_prefs.epbin if vi_prefs and vi_prefs.epbin and os.path.isdir(vi_prefs.epbin) else os.path.join('{}'.format(addonpath), 'EPFiles')
    radldir = vi_prefs.radlib if vi_prefs and os.path.isdir(vi_prefs.radlib) else os.path.join('{}'.format(addonpath), 'Radfiles', 'lib')
    radbdir = vi_prefs.radbin if vi_prefs and os.path.isdir(vi_prefs.radbin) else os.path.join('{}'.format(addonpath), 'Radfiles', 'bin')
    ofbdir = vi_prefs.ofbin if vi_prefs and os.path.isdir(vi_prefs.ofbin) else os.path.join('{}'.format(addonpath), 'OFFiles', 'bin')
    ofldir = vi_prefs.oflib if vi_prefs and os.path.isdir(vi_prefs.oflib) else os.path.join('{}'.format(addonpath), 'OFFiles', 'lib')
    ofedir = vi_prefs.ofetc if vi_prefs and os.path.isdir(vi_prefs.ofetc) else os.path.join('{}'.format(addonpath), 'OFFiles')
    os.environ["PATH"] += "{0}{1}".format(evsep[str(sys.platform)], os.path.dirname(bpy.app.binary_path))

    if not os.environ.get('RAYPATH'):# or radldir not in os.environ['RAYPATH'] or radbdir not in os.environ['PATH']  or epdir not in os.environ['PATH']:
        if vi_prefs and os.path.isdir(vi_prefs.radlib):
            os.environ["RAYPATH"] = '{0}{1}{2}'.format(radldir, evsep[str(sys.platform)], os.path.join(addonpath, 'Radfiles', 'lib'))
        else:
            os.environ["RAYPATH"] = radldir

        os.environ["PATH"] = os.environ["PATH"] + "{0}{1}{0}{2}{0}{3}".format(evsep[str(sys.platform)], radbdir, epdir, ofbdir)
        os.environ["LD_LIBRARY_PATH"] = os.environ["LD_LIBRARY_PATH"] + "{0}{1}".format(evsep[str(sys.platform)], ofldir) if os.environ.get("LD_LIBRARY_PATH") else "{0}{1}".format(evsep[str(sys.platform)], ofldir)
        os.environ["WM_PROJECT_DIR"] = ofedir
        
def colupdate(self, context):
    cmap(self)

def confunc(i):
    confuncdict = {'0': envi_cons.wall_con.keys(), '1': envi_cons.floor_con.keys(), '2': envi_cons.roof_con.keys(),
    '3': envi_cons.door_con.keys(), '4': envi_cons.glaze_con.keys()}
    return [((con, con, 'Contruction type')) for con in list(confuncdict[str(i)])]

(wallconlist, floorconlist, roofconlist, doorconlist, glazeconlist) = [confunc(i) for i in range(5)]

def eupdate(self, context):
    scene = context.scene
    maxo, mino = scene.vi_leg_max, scene.vi_leg_min
    odiff = scene.vi_leg_max - scene.vi_leg_min

    if context.active_object.mode == 'EDIT':
        return
    if odiff:
        for frame in range(scene['liparams']['fs'], scene['liparams']['fe'] + 1):
            for o in [obj for obj in bpy.data.objects if obj.lires == 1 and obj.data.shape_keys and str(frame) in [sk.name for sk in obj.data.shape_keys.key_blocks]]:
                bm = bmesh.new()
                bm.from_mesh(o.data)
                bm.transform(o.matrix_world)
                skb = bm.verts.layers.shape['Basis']
                skf = bm.verts.layers.shape[str(frame)]

                if str(frame) in o['omax']:
                    if bm.faces.layers.float.get('res{}'.format(frame)):
                        extrude = bm.faces.layers.int['extrude']
                        res = bm.faces.layers.float['res{}'.format(frame)] #if context.scene['cp'] == '0' else bm.verts.layers.float['res{}'.format(frame)]
                        faces = [f for f in bm.faces if f[extrude]]
                        fnorms = array([f.normal.normalized() for f in faces]).T
                        fres = array([f[res] for f in faces])
                        extrudes = (0.1 * scene.vi_disp_3dlevel * (nlog10(maxo * (fres + 1 - mino)/odiff)) * fnorms).T if scene.vi_leg_scale == '1' else \
                            multiply(fnorms, scene.vi_disp_3dlevel * ((fres - mino)/odiff)).T

                        for f, face in enumerate(faces):
                            for v in face.verts:
                                v[skf] = v[skb] + mathutils.Vector(extrudes[f])

                    elif bm.verts.layers.float.get('res{}'.format(frame)):
                        res = bm.verts.layers.float['res{}'.format(frame)]
                        vnorms = array([v.normal.normalized() for v in bm.verts]).T
                        vres = array([v[res] for v in bm.verts])
                        extrudes = multiply(vnorms, scene.vi_disp_3dlevel * ((vres-mino)/odiff)).T if scene.vi_leg_scale == '0' else \
                            [0.1 * scene.vi_disp_3dlevel * (math.log10(maxo * (v[res] + 1 - mino)/odiff)) * v.normal.normalized() for v in bm.verts]
                        for v, vert in enumerate(bm.verts):
                            vert[skf] = vert[skb] + mathutils.Vector(extrudes[v])

                bm.transform(o.matrix_world.inverted())
                bm.to_mesh(o.data)
                bm.free()

def tupdate(self, context):
    for o in [o for o in context.scene.objects if o.type == 'MESH'  and 'lightarray' not in o.name and o.hide == False and o.layers[context.scene.active_layer] == True and o.get('lires')]:
        o.show_transparent = 1
    for mat in [bpy.data.materials['{}#{}'.format('vi-suite', index)] for index in range(20)]:
        mat.use_transparency, mat.transparency_method, mat.alpha = 1, 'MASK', context.scene.vi_disp_trans
    cmap(self)

def wupdate(self, context):
    o = context.active_object
    if o and o.type == 'MESH':
        (o.show_wire, o.show_all_edges) = (1, 1) if context.scene.vi_disp_wire else (0, 0)

def legupdate(self, context):
    scene = context.scene
    frames = range(scene['liparams']['fs'], scene['liparams']['fe'] + 1)
    obs = [o for o in scene.objects if o.get('lires')]

    if scene.vi_leg_scale == '0':
        bins = array([0.05 * i for i in range(1, 20)])
    elif scene.vi_leg_scale == '1':
        slices = logspace(0, 2, 21, True)
        bins = array([(slices[i] - 0.05 * (20 - i))/100 for i in range(21)])
        bins = array([1 - math.log10(i)/math.log10(21) for i in range(1, 22)][::-1])
        bins = bins[1:-1]

    for o in obs:
        bm = bmesh.new()
        bm.from_mesh(o.data)

        for f, frame in enumerate(frames):
            if bm.faces.layers.float.get('res{}'.format(frame)):
                livires = bm.faces.layers.float['res{}'.format(frame)]
                ovals = array([f[livires] for f in bm.faces])
            elif bm.verts.layers.float.get('res{}'.format(frame)):
                livires = bm.verts.layers.float['res{}'.format(frame)]
                ovals = array([sum([vert[livires] for vert in f.verts])/len(f.verts) for f in bm.faces])

            if scene.vi_leg_max > scene.vi_leg_min:
                vals = ovals - scene.vi_leg_min
                vals = vals/(scene.vi_leg_max - scene.vi_leg_min)
            else:
                vals = array([scene.vi_leg_max for f in bm.faces])

            nmatis = digitize(vals, bins)

            if len(frames) == 1:
                o.data.polygons.foreach_set('material_index', nmatis)
                o.data.update()

            elif len(frames) > 1:
                for fi, fc in enumerate(o.data.animation_data.action.fcurves):
                    fc.keyframe_points[f].co = frame, nmatis[fi]
        bm.free()
    scene.frame_set(scene.frame_current)

def liviresupdate(self, context):
    setscenelivivals(context.scene)
    for o in [o for o in bpy.data.objects if o.lires]:
        o.lividisplay(context.scene)
    eupdate(self, context)

def register():
    bpy.utils.register_module(__name__)
    Object, Scene, Material = bpy.types.Object, bpy.types.Scene, bpy.types.Material

# VI-Suite object definitions
    Object.vi_type = eprop([("0", "None", "Not a VI-Suite zone"), ("1", "EnVi Zone", "Designates an EnVi Thermal zone"),
                            ("2", "CFD Domain", "Specifies an OpenFoam BlockMesh"), ("3", "CFD Geometry", "Specifies an OpenFoam geometry"),
                            ("4", "Light Array", "Specifies a LiVi lighting array"), ("5", "Complex Fenestration", "Specifies complex fenestration for BSDF generation")], "", "Specify the type of VI-Suite zone", "0")

# LiVi object properties
    Object.livi_merr = bprop("LiVi simple mesh export", "Boolean for simple mesh export", False)
    Object.ies_name = bpy.props.StringProperty(name="", description="Name of the IES file", default="", subtype="FILE_PATH")
    Object.ies_strength = fprop("", "Strength of IES lamp", 0, 1, 1)
    Object.ies_unit = eprop([("m", "Meters", ""), ("c", "Centimeters", ""), ("f", "Feet", ""), ("i", "Inches", "")], "", "Specify the IES file measurement unit", "m")
    Object.ies_colmenu = eprop([("0", "RGB", ""), ("1", "Temperature", "")], "", "Specify the IES colour type", "0")
    Object.ies_rgb = fvprop(3, "",'IES Colour', [1.0, 1.0, 1.0], 'COLOR', 0, 1)
    Object.ies_ct = iprop("", "Colour temperature in Kelven", 0, 12000, 4700)
    (Object.licalc, Object.lires, Object.limerr, Object.manip, Object.bsdf_proxy) = [bprop("", "", False)] * 5
    Object.compcalcapply = compcalcapply
    Object.basiccalcapply = basiccalcapply
    Object.rtpoints = rtpoints
    Object.udidacalcapply = udidacalcapply
    Object.lividisplay = lividisplay
    Object.lhcalcapply = lhcalcapply
    Object.li_bsdf_direc = EnumProperty(items = [('+b -f', 'Backwards', 'Backwards BSDF'), ('+f -b', 'Forwards', 'Forwards BSDF'), ('+b +f', 'Bi-directional', 'Bi-directional BSDF')], name = '', description = 'BSDF direction', default = '+b -f')
    Object.li_bsdf_tensor = EnumProperty(items = [(' ', 'Klems', 'Uniform Klems sample'), ('-t3', 'Symmentric', 'Symmetric Tensor BSDF'), ('-t4', 'Assymmetric', 'Asymmetric Tensor BSDF')], name = '', description = 'BSDF tensor', default = ' ')
    Object.li_bsdf_res = EnumProperty(items = [('1', '2x2', '2x2 sampling resolution'), ('2', '4x4', '4x4 sampling resolution'), ('3', '8x8', '8x8 sampling resolution'), ('4', '16x16', '16x16 sampling resolution'), ('5', '32x32', '32x32 sampling resolution'), ('6', '64x64', '64x64 sampling resolution'), ('7', '128x128', '128x128 sampling resolution')], name = '', description = 'BSDF resolution', default = '4')
    Object.li_bsdf_tsamp = bpy.props.IntProperty(name = '', description = 'Tensor samples', min = 1, max = 20, default = 4)
    Object.li_bsdf_ksamp = bpy.props.IntProperty(name = '', description = 'Klem samples', min = 1, default = 200)
    Object.li_bsdf_rcparam = sprop("", "rcontrib parameters", 1024, "")
    Object.radbsdf = radbsdf
    Object.retsv = retsv

# EnVi zone definitions
    Object.envi_type = eprop([("0", "Thermal", "Thermal Zone"), ("1", "Shading", "Shading Object"), ("2", "Chimney", "Thermal Chimney Object")], "EnVi object type", "Specify the EnVi object type", "0")
    Object.envi_oca = eprop([("0", "Default", "Use the system wide convection algorithm"), ("1", "Simple", "Use the simple convection algorithm"), ("2", "TARP", "Use the detailed convection algorithm"), ("3", "DOE-2", "Use the Trombe wall convection algorithm"), ("4", "MoWitt", "Use the adaptive convection algorithm"), ("5", "Adaptive", "Use the adaptive convection algorithm")], "", "Specify the EnVi zone outside convection algorithm", "0")
    Object.envi_ica = eprop([("0", "Default", "Use the system wide convection algorithm"), ("1", "Simple", "Use the simple convection algorithm"), ("2", "Detailed", "Use the detailed convection algorithm"), ("3", "Trombe", "Use the Trombe wall convection algorithm"), ("4", "Adaptive", "Use the adaptive convection algorithm")], "", "Specify the EnVi zone inside convection algorithm", "0")

# FloVi object definitions

# Vi_suite material definitions
    Material.mattype = eprop([("0", "Geometry", "Geometry"), ("1", 'Light sensor', "LiVi sensing material".format(u'\u00b3')), ("2", "FloVi boundary", 'FloVi blockmesh boundary')], "", "VI-Suite material type", "0")

# LiVi material definitions
    Material.radmat = radmat
    Material.radmatdict = {'0': ['radcolour', 0, 'radrough', 'radspec'], '1': ['radcolour'], '2': ['radcolour', 0, 'radior'], '3': ['radcolour', 0, 'radspec', 'radrough', 0, 'radtrans',  'radtranspec'], '4': ['radcolour'],
    '5': ['radcolmenu', 0, 'radcolour', 0, 'radct',  0, 'radintensity'], '6': ['radcolour', 0, 'radrough', 'radspec'], '7': [], '8': [], '9': []}
    Material.pport = bprop("", "Flag to signify whether the material represents a Photon Port", False)
    Material.radtex = bprop("", "Flag to signify whether the material has a texture associated with it", False)
    Material.radnorm = bprop("", "Flag to signify whether the material has a normal map associated with it", False)
    Material.ns = fprop("", "Strength of normal effect", 0, 5, 1)
    Material.nu = fvprop(3, '', 'Image up vector', [0, 0, 1], 'VELOCITY', -1, 1)
    Material.nside = fvprop(3, '', 'Image side vector', [-1, 0, 0], 'VELOCITY', -1, 1)
    radtypes = [('0', 'Plastic', 'Plastic Radiance material'), ('1', 'Glass', 'Glass Radiance material'), ('2', 'Dielectric', 'Dialectric Radiance material'),
                ('3', 'Translucent', 'Translucent Radiance material'), ('4', 'Mirror', 'Mirror Radiance material'), ('5', 'Light', 'Emission Radiance material'),
                ('6', 'Metal', 'Metal Radiance material'), ('7', 'Anti-matter', 'Antimatter Radiance material'), ('8', 'BSDF', 'BSDF Radiance material'), ('9', 'Custom', 'Custom Radiance material')]
    Material.radmatmenu = eprop(radtypes, "", "Type of Radiance material", '0')
    Material.radcolour = fvprop(3, "Material Colour",'Material Colour', [0.8, 0.8, 0.8], 'COLOR', 0, 1)
    Material.radcolmenu = eprop([("0", "RGB", "Specify colour temperature"), ("1", "Temperature", "Specify colour temperature")], "Colour type:", "Specify the colour input", "0")
    Material.radrough = fprop("Roughness", "Material roughness", 0, 1, 0.1)
    Material.radspec = fprop("Specularity", "Material specular reflection", 0, 1, 0.0)
    Material.radtrans = fprop("Transmission", "Material diffuse transmission", 0, 1, 0.1)
    Material.radtranspec  = fprop("Trans spec", "Material specular transmission", 0, 1, 0.1)
    Material.radior  = fprop("IOR", "Material index of refractionn", 0, 5, 1.5)
    Material.radct = iprop("Temperature (K)", "Colour temperature in Kelven", 0, 12000, 4700)
    Material.radintensity = fprop("Intensity", u"Material radiance (W/sr/m\u00b2)", 0, 100, 1)
    Material.radfile = sprop("", "Radiance file material description", 1024, "")
    Material.vi_shadow = bprop("VI Shadow", "Flag to signify whether the material represents a VI Shadow sensing surface", False)
    Material.livi_sense = bprop("LiVi Sensor", "Flag to signify whether the material represents a LiVi sensing surface", False)
    Material.livi_compliance = bprop("LiVi Compliance Surface", "Flag to siginify whether the material represents a LiVi compliance surface", False)
    Material.gl_roof = bprop("Glazed Roof", "Flag to siginify whether the communal area has a glazed roof", False)
    hspacetype = [('0', 'Public/Staff', 'Public/Staff area'), ('1', 'Patient', 'Patient area')]
    rspacetype = [('0', "Kitchen", "Kitchen space"), ('1', "Living/Dining/Study", "Living/Dining/Study area"), ('2', "Communal", "Non-residential or communal area")]
    respacetype = [('0', "Sales", "Sales space"), ('1', "Occupied", "Occupied space")]
    lespacetype = [('0', "Healthcare", "Healthcare space"), ('1', "Other", "Other space")]

    Material.hspacemenu = eprop(hspacetype, "", "Type of healthcare space", '0')
    Material.brspacemenu = eprop(rspacetype, "", "Type of residential space", '0')
    Material.crspacemenu = eprop(rspacetype[:2], "", "Type of residential space", '0')
    Material.respacemenu = eprop(respacetype, "", "Type of retail space", '0')
    Material.lespacemenu = eprop(lespacetype, "", "Type of space", '0')
    Material.BSDF = bprop("", "Flag to signify a BSDF material", False)

# EnVi material definitions
    Material.envi_nodes = bpy.props.PointerProperty(type = bpy.types.NodeTree)
    Material.envi_type = sprop("", "EnVi Material type", 64, "None")

    Material.envi_shading = bprop("", "Flag to siginify whether the material contains shading elements", False)
#    Material.envi_con_type = eprop([("Wall", "Wall", "Wall construction"),("Floor", "Floor", "Ground floor construction"),("Roof", "Roof", "Roof construction"),("Ceiling", "Ceiling", "Ceiling construction"),("Window", "Window", "Window construction"), ("Door", "Door", "Door construction"),
#                    ("Shading", "Shading", "Shading material"),("None", "None", "Surface to be ignored")], "", "Specify the construction type", "None")
#    Material.envi_simple_glazing = bprop("", "Flag to siginify whether to use a EP simple glazing representation", False)
#    Material.envi_sg_uv = fprop("", "Window U-Value", 0, 10, 2.4)
#    Material.envi_sg_shgc = fprop("", "Window Solar Heat Gain Coefficient", 0, 1, 0.7)
#    Material.envi_sg_vt = fprop("", "Window Visible Transmittance", 0, 1, 0.8)
    Material.envi_boundary = bprop("", "Flag to siginify whether the material represents a zone boundary", False)
#    Material.envi_afsurface = bprop("", "Flag to siginify whether the material represents an airflow surface", False)
#    Material.envi_thermalmass = bprop("", "Flag to siginify whether the material represents thermal mass", False)
#    Material.envi_aperture = eprop([("0", "External", "External facade airflow component", 0), ("1", "Internal", "Zone boundary airflow component", 1),], "", "Position of the airflow component", "0")
#    Material.envi_con_makeup = eprop([("0", "Pre-set", "Construction pre-set"),("1", "Layers", "Custom layers"),("2", "Dummy", "Adiabatic")], "", "Pre-set construction of custom layers", "0")
#    Material.envi_layero = eprop([("0", "None", "Not present"), ("1", "Database", "Select from database"), ("2", "Custom", "Define custom material properties")], "", "Composition of the outer layer", "0")
#    Material.envi_type_lo = bpy.props.EnumProperty(items = envi_layerotype, name = "", description = "Outer layer material type")
#    Material.envi_type_l1 = bpy.props.EnumProperty(items = envi_layer1type, name = "", description = "Second layer material type")
#    Material.envi_type_l2 = bpy.props.EnumProperty(items = envi_layer2type, name = "", description = "Third layer material type")
#    Material.envi_type_l3 = bpy.props.EnumProperty(items = envi_layer3type, name = "", description = "Fourth layer material type")
#    Material.envi_type_l4 = bpy.props.EnumProperty(items = envi_layer4type, name = "", description = "Fifth layer material type")
#    (Material.envi_layer1, Material.envi_layer2, Material.envi_layer3, Material.envi_layer4) = \
#    [eprop([("0", "None", "Not present"),("1", "Database", "Select from database"), ("2", "Custom", "Define custom material properties")], "", "Composition of the next layer", "0")] * (conlayers - 1)
    Material.envi_export = bprop("Material Export", "Flag to tell EnVi to export this material", False)
#    Material.envi_material_lo = bpy.props.EnumProperty(items = envi_layero, name = "", description = "Outer layer material")
#    Material.envi_material_l1 = bpy.props.EnumProperty(items = envi_layer1, name = "", description = "Second layer material")
#    Material.envi_material_l2 = bpy.props.EnumProperty(items = envi_layer2, name = "", description = "Third layer material")
#    Material.envi_material_l3 = bpy.props.EnumProperty(items = envi_layer3, name = "", description = "Fourth layer material")
#    Material.envi_material_l4 = bpy.props.EnumProperty(items = envi_layer4, name = "", description = "Fifth layer material")
#    Material.envi_con_list = bpy.props.EnumProperty(items = envi_con_list, name = "", description = "Database construction")
#    Material.envi_material_uv = sprop("", "Material U-value (non-film)", 64, "N/A")
#    (Material.envi_export_lo_name, Material.envi_export_l1_name, Material.envi_export_l2_name, Material.envi_export_l3_name, Material.envi_export_l4_name) = \
#    [sprop("", "Layer name", 0, "")] * conlayers
#    (Material.envi_export_lo_tc, Material.envi_export_l1_tc, Material.envi_export_l2_tc, Material.envi_export_l3_tc, Material.envi_export_l4_tc) = \
#    [fprop("Conductivity", "Thermal Conductivity", 0, 10, 0.5)] * conlayers
#    (Material.envi_export_lo_rough, Material.envi_export_l1_rough, Material.envi_export_l2_rough, Material.envi_export_l3_rough, Material.envi_export_l4_rough) = \
#    [eprop([("VeryRough", "VeryRough", "Roughness"), ("Rough", "Rough", "Roughness"), ("MediumRough", "MediumRough", "Roughness"),
#                                                        ("MediumSmooth", "MediumSmooth", "Roughness"), ("Smooth", "Smooth", "Roughness"), ("VerySmooth", "VerySmooth", "Roughness")],
#                                                        "Material surface roughness", "specify the material rughness for convection calculations", "Rough")] * conlayers
#
#    (Material.envi_export_lo_rho, Material.envi_export_l1_rho, Material.envi_export_l2_rho, Material.envi_export_l3_rho, Material.envi_export_l4_rho) = \
#    [fprop("Density", "Density (kg/m3)", 0, 10000, 1000)] * conlayers
#    (Material.envi_export_lo_shc, Material.envi_export_l1_shc, Material.envi_export_l2_shc, Material.envi_export_l3_shc, Material.envi_export_l4_shc) = \
#    [fprop("SHC", "Specific Heat Capacity (J/kgK)", 0, 10000, 1000)] * conlayers
#    (Material.envi_export_lo_thi, Material.envi_export_l1_thi, Material.envi_export_l2_thi, Material.envi_export_l3_thi, Material.envi_export_l4_thi) = \
#    [fprop("mm", "Thickness (mm)", 1, 10000, 100)] * conlayers
#    (Material.envi_export_lo_tab, Material.envi_export_l1_tab, Material.envi_export_l2_tab, Material.envi_export_l3_tab, Material.envi_export_l4_tab) = \
#    [fprop("TA", "Thermal Absorptance", 0.001, 1, 0.8)] * conlayers
#    (Material.envi_export_lo_sab, Material.envi_export_l1_sab, Material.envi_export_l2_sab, Material.envi_export_l3_sab, Material.envi_export_l4_sab) = \
#    [fprop("SA", "Solar Absorptance", 0.001, 1, 0.6)] * conlayers
#    (Material.envi_export_lo_vab, Material.envi_export_l1_vab, Material.envi_export_l2_vab, Material.envi_export_l3_vab, Material.envi_export_l4_vab) = \
#    [fprop("VA", "Visible Absorptance", 0.001, 1, 0.6)] * conlayers
#    (Material.envi_export_lo_odt, Material.envi_export_l1_odt, Material.envi_export_l2_odt, Material.envi_export_l3_odt, Material.envi_export_l4_odt) = \
#    [eprop([("SpectralAverage", "SpectralAverage", "Optical Data Type")], "", "Optical Data Type", "SpectralAverage")] * conlayers
#    (Material.envi_export_lo_sds, Material.envi_export_l1_sds, Material.envi_export_l2_sds, Material.envi_export_l3_sds, Material.envi_export_l4_sds) = \
#    [eprop([("0", "", "Window Glass Spectral Data Set Name")], "", "Window Glass Spectral Data Set Name", "0")] * conlayers
#    (Material.envi_export_lo_stn, Material.envi_export_l1_stn, Material.envi_export_l2_stn, Material.envi_export_l3_stn, Material.envi_export_l4_stn) = \
#    [fprop("STN", "Solar Transmittance at Normal Incidence", 0, 1, 0.9)] * conlayers
#    (Material.envi_export_lo_fsn, Material.envi_export_l1_fsn, Material.envi_export_l2_fsn, Material.envi_export_l3_fsn, Material.envi_export_l4_fsn) = \
#    [fprop("FSN", "Front Side Solar Reflectance at Normal Incidence", 0, 1, 0.075)] * conlayers
#    (Material.envi_export_lo_bsn, Material.envi_export_l1_bsn, Material.envi_export_l2_bsn, Material.envi_export_l3_bsn, Material.envi_export_l4_bsn) = \
#    [fprop("BSN", "Back Side Solar Reflectance at Normal Incidence", 0, 1, 0.075)] * conlayers
#    (Material.envi_export_lo_vtn, Material.envi_export_l1_vtn, Material.envi_export_l2_vtn, Material.envi_export_l3_vtn, Material.envi_export_l4_vtn) = \
#    [fprop("VTN", "Visible Transmittance at Normal Incidence", 0, 1, 0.9)] * conlayers
#    (Material.envi_export_lo_fvrn, Material.envi_export_l1_fvrn, Material.envi_export_l2_fvrn, Material.envi_export_l3_fvrn, Material.envi_export_l4_fvrn) = \
#    [fprop("FVRN", "Front Side Visible Reflectance at Normal Incidence", 0, 1, 0.08)] * conlayers
#    (Material.envi_export_lo_bvrn, Material.envi_export_l1_bvrn, Material.envi_export_l2_bvrn, Material.envi_export_l3_bvrn, Material.envi_export_l4_bvrn) = \
#    [fprop("BVRN", "Back Side Visible Reflectance at Normal Incidence", 0, 1, 0.08)] * conlayers
#    (Material.envi_export_lo_itn, Material.envi_export_l1_itn, Material.envi_export_l2_itn, Material.envi_export_l3_itn, Material.envi_export_l4_itn) = \
#    [fprop("ITN", "Infrared Transmittance at Normal Incidence", 0, 1, 0.0)] * conlayers
#    (Material.envi_export_lo_fie, Material.envi_export_l1_fie, Material.envi_export_l2_fie, Material.envi_export_l3_fie, Material.envi_export_l4_fie) = \
#    [fprop("FIE", "Front Side Infrared Hemispherical Emissivity", 0, 1, 0.84)] * conlayers
#    (Material.envi_export_lo_bie, Material.envi_export_l1_bie, Material.envi_export_l2_bie, Material.envi_export_l3_bie, Material.envi_export_l4_bie) = \
#    [fprop("BIE", "Back Side Infrared Hemispherical Emissivity", 0, 1, 0.84)] * conlayers
#    (Material.envi_export_lo_sdiff, Material.envi_export_l1_sdiff, Material.envi_export_l2_sdiff, Material.envi_export_l3_sdiff, Material.envi_export_l4_sdiff) = \
#    [bprop("", "", 0)] * conlayers
#    Material.envi_shad_att = bprop("Attached", "Flag to specify shading attached to the building",False)
#    (Material.envi_tctc_lo, Material.envi_tctc_l1, Material.envi_tctc_l2, Material.envi_tctc_l3, Material.envi_tctc_l4) = [fprop("", "Temperature coefficient for thermal conductivity", 0, 50, 0.0)] * conlayers
#    (Material.envi_tempsemps_lo, Material.envi_tempsemps_l1, Material.envi_tempsemps_l2, Material.envi_tempsemps_l3, Material.envi_tempsemps_l4) = [sprop("", "Temperatures/Enthalpy pairs", 1024, "")] * conlayers

# FloVi material definitions
    Material.fvmat = fvmat
    Material.flovi_bmb_type = eprop([("0", "Patch", "Wall boundary"), ("1", "Wall", "Inlet boundary"), ("2", "Symmetry", "Symmetry plane boundary"), ("3", "Empty", "Empty boundary")], "", "FloVi blockmesh boundary type", "0")
#    Material.flovi_bmb_type = eprop([("0", "Wall", "Wall boundary"), ("1", "Inlet", "Inlet boundary"), ("2", "Outlet", "Outlet boundary"), ("3", "Symmetry", "Symmetry boundary"), ("4", "Empty", "Empty boundary")], "", "FloVi blockmesh boundary type", "0")

    Material.flovi_bmbp_subtype = EnumProperty(items = ret_fvbp_menu, name = "", description = "FloVi sub-type boundary")
    Material.flovi_bmbp_val = fprop("", "Pressure value", -1000, 1000, 0.0)
    Material.flovi_p_field = bprop("", "Take boundary velocity from the field velocity", False)
    Material.flovi_bmbp_p0val = fprop("", "Pressure value", -1000, 1000, 0)
    Material.flovi_bmbp_gamma = fprop("", "Pressure value", -1000, 1000, 1.4)

    Material.flovi_bmbu_subtype = EnumProperty(items = ret_fvbu_menu, name = "", description = "FloVi sub-type boundary")
    Material.flovi_bmbu_val = fvprop(3, '', 'Vector value', [0, 0, 0], 'VELOCITY', -100, 100)
    Material.flovi_u_field = bprop("", "Take boundary velocity from the field velocity", False)

    Material.flovi_bmbnut_subtype = EnumProperty(items = ret_fvbnut_menu, name = "", description = "FloVi sub-type boundary")
    Material.flovi_bmbnut_val = fprop("", "Nut value", -1000, 1000, 0.0)
    Material.flovi_nut_field = bprop("", "Take boundary nut from the field nut", False)

    Material.flovi_bmbk_subtype = EnumProperty(items = ret_fvbk_menu, name = "", description = "FloVi sub-type boundary")
    Material.flovi_bmbk_val = fprop("", "k value", -1000, 1000, 0.0)
    Material.flovi_k_field = bprop("", "Take boundary k from the field k", False)

    Material.flovi_bmbe_subtype = EnumProperty(items = ret_fvbepsilon_menu, name = "", description = "FloVi sub-type boundary")
    Material.flovi_bmbe_val = fprop("", "Epsilon value", -1000, 1000, 0.0)
    Material.flovi_e_field = bprop("", "Take boundary epsilon from the field epsilon", False)

    Material.flovi_bmbo_subtype = EnumProperty(items = ret_fvbomega_menu, name = "", description = "FloVi sub-type boundary")
    Material.flovi_bmbo_val = fprop("", "Omega value", -1000, 1000, 0.0)
    Material.flovi_o_field = bprop("", "Take boundary omega from the field omega", False)

    Material.flovi_bmbnutilda_subtype = EnumProperty(items = ret_fvbnutilda_menu, name = "", description = "FloVi sub-type boundary")
    Material.flovi_bmbnutilda_val = fprop("", "NuTilda value", -1000, 1000, 0.0)
    Material.flovi_nutilda_field = bprop("", "Take boundary nutilda from the field nutilda", False)

    Material.flovi_bmbt_subtype = EnumProperty(items = ret_fvbt_menu, name = "", description = "FloVi sub-type boundary")
    Material.flovi_bmbt_val = fprop("", "T value", -1000, 1000, 0.0)
    Material.flovi_t_field = bprop("", "Take boundary t from the field t", False)

    Material.flovi_bmba_subtype = EnumProperty(items = ret_fvba_menu, name = "", description = "FloVi sub-type boundary")
    Material.flovi_bmba_val = fprop("", "T value", -1000, 1000, 0.0)
    Material.flovi_a_field = bprop("", "Take boundary alphat from the field alphat", False)

    Material.flovi_bmbprgh_subtype = EnumProperty(items = ret_fvbprgh_menu, name = "", description = "FloVi sub-type boundary")
    Material.flovi_bmbprgh_val = fprop("", "p_rgh value", -1000, 1000, 0.0)
    Material.flovi_prgh_field = bprop("", "Take boundary p_rgh from the field p_rgh", False)
#    Material.flovi_bmpp_type = eprop([("zeroGradient", "Zero Gradient", "Zero gradient boundary")], "", "FloVi wall boundary type", "zeroGradient")
#    Material.flovi_bmwp_type = eprop([("zeroGradient", "Zero Gradient", "Zero gradient boundary")], "", "FloVi wall boundary type", "zeroGradient")
#    Material.flovi_bmwu_type = eprop([("fixedValue", "Fixed", "Fixed value boundary"), ("slip", "Slip", "Slip boundary")], "", "FloVi wall boundary type", "fixedValue")
#    Material.flovi_bmwnutilda_type = eprop([("fixedValue", "Fixed", "Fixed value boundary")], "", "FloVi wall boundary type", "fixedValue")
#    Material.flovi_bmwnut_type = eprop([("nutUSpaldingWallFunction", "SpaldingWF", "Fixed value boundary"), ("nutkWallFunction", "k wall function", "Fixed value boundary")], "", "FloVi wall boundary type", "nutUSpaldingWallFunction")
#    Material.flovi_bmwk_type = eprop([("kqRWallFunction", "kqRWallFunction", "Fixed value boundary")], "", "FloVi wall boundary type", "kqRWallFunction")
#    Material.flovi_bmwe_type = eprop([("epsilonWallFunction", "epsilonWallFunction", "Fixed value boundary")], "", "FloVi wall boundary type", "epsilonWallFunction")
#    Material.flovi_bmwo_type = eprop([("omegaWallFunction", "omegaWallFunction", "Fixed value boundary")], "", "FloVi wall boundary type", "omegaWallFunction")
#
#    Material.flovi_bmu_x = fprop("X", "Value in the X-direction", -1000, 1000, 0.0)
#    Material.flovi_bmu_y = fprop("Y", "Value in the Y-direction", -1000, 1000, 0.0)
#    Material.flovi_bmu_z = fprop("Z", "Value in the Z-direction", -1000, 1000, 0.0)
#
##    Material.flovi_bmwnut_y = fprop("Y", "Value in the Y-direction", -1000, 1000, 0.0)
##    Material.flovi_bmwnut_z = fprop("Z", "Value in the Z-direction", -1000, 1000, 0.0)
#    Material.flovi_bmip_type = eprop([("zeroGradient", "Zero Gradient", "Zero gradient pressure boundary"), ("freestreamPressure", "Freestream Pressure", "Free stream pressure gradient boundary")], "", "FloVi wall boundary type", "zeroGradient")
#    Material.flovi_bmiop_val = fprop("X", "Pressure value", -1000, 1000, 0.0)
#    Material.flovi_bmop_type = eprop([("zeroGradient", "Zero Gradient", "Zero gradient pressure boundary"), ("freestreamPressure", "Freestream Pressure", "Free stream pressure gradient boundary"), ("fixedValue", "FixedValue", "Fixed value pressure boundary")], "", "FloVi wall boundary type", "zeroGradient")
#    Material.flovi_bmiu_type = eprop([("freestream", "Freestream velocity", "Freestream velocity boundary"), ("fixedValue", "Fixed Value", "Fixed velocity boundary")], "", "FloVi wall boundary type", "fixedValue")
#    Material.flovi_bmou_type = eprop([("freestream", "Freestream velocity", "Freestream velocity boundary"), ("zeroGradient", "Zero Gradient", "Zero gradient  boundary"), ("fixedValue", "Fixed Value", "Fixed velocity boundary")], "", "FloVi wall boundary type", "zeroGradient")
#    Material.flovi_bminut_type = eprop([("calculated", "Calculated", "Calculated value boundary")], "", "FloVi wall boundary type", "calculated")
#    Material.flovi_bmonut_type = eprop([("calculated", "Calculated", "Calculated value boundary")], "", "FloVi wall boundary type", "calculated")
#    Material.flovi_bminutilda_type = eprop([("freeStream", "Freestream", "Free stream value boundary")], "", "FloVi wall boundary type", "freeStream")
#    Material.flovi_bmonutilda_type = eprop([("freeStream", "Freestream", "Free stream value boundary")], "", "FloVi wall boundary type", "freeStream")
#    Material.flovi_bmik_type = eprop([("fixedValue", "Fixed Value", "Fixed value boundary")], "", "FloVi wall boundary type", "fixedValue")
#    Material.flovi_bmok_type = eprop([("inletOutlet", "Inlet/outlet", "Inlet/outlet boundary")], "", "FloVi wall boundary type", "inletOutlet")
#    Material.flovi_bmie_type = eprop([("fixedValue", "Fixed Value", "Fixed value boundary")], "", "FloVi wall boundary type", "fixedValue")
#    Material.flovi_bmoe_type = eprop([("inletOutlet", "Inlet/outlet", "Inlet/outlet boundary")], "", "FloVi wall boundary type", "inletOutlet")
#    Material.flovi_bmio_type = eprop([("zeroGradient", "Zero Gradient", "Zero gradient boundary")], "", "FloVi wall boundary type", "zeroGradient")
#    Material.flovi_bmoo_type = eprop([("fixedValue", "Fixed", "Fixed value boundary")], "", "FloVi wall boundary type", "fixedValue")
#    Material.flovi_bmwt_type = eprop([("zeroGradient", "Zero Gradient", "Zero gradient boundary"), ("fixedValue", "Fixed", "Fixed value boundary")], "", "FloVi temperature boundary type", "zeroGradient")
#    Material.flovi_bmit_type = eprop([("zeroGradient", "Zero Gradient", "Zero gradient boundary"), ("fixedValue", "Fixed", "Fixed value boundary")], "", "FloVi temperature boundary type", "zeroGradient")
#    Material.flovi_bmot_type = eprop([("zeroGradient", "Zero Gradient", "Zero gradient boundary"), ("fixedValue", "Fixed", "Fixed value boundary")], "", "FloVi temperature boundary type", "zeroGradient")
#    Material.flovi_bmiu_x = fprop("X", "Value in the X-direction", -1000, 1000, 0.0)
#    Material.flovi_bmiu_y = fprop("Y", "Value in the Y-direction", -1000, 1000, 0.0)
#    Material.flovi_bmiu_z = fprop("Z", "Value in the Z-direction", -1000, 1000, 0.0)
#    Material.flovi_bmou_x = fprop("X", "Value in the X-direction", -1000, 1000, 0.0)
#    Material.flovi_bmou_y = fprop("Y", "Value in the Y-direction", -1000, 1000, 0.0)
#    Material.flovi_bmou_z = fprop("Z", "Value in the Z-direction", -1000, 1000, 0.0)
#    Material.flovi_temp = fprop("K", "Temperature", 0, 500, 0.0)
#    Material.flovi_bmnut = fprop("", "nuTilda value", -1000, 1000, 0.0)
#    Material.flovi_bmk = fprop("", "k value", 0, 1000, 0.0)
#    Material.flovi_bme = fprop("", "Epsilon value", 0, 1000, 0.0)
#    Material.flovi_bmo = fprop("", "Omega value", 0, 1000, 0.0)
    Material.flovi_ground = bprop("", "Ground material", False)
#    Material.flovi_b_sval = fprop("", "Scalar value", -500, 500, 0.0)
#    Material.flovi_b_vval = fvprop(3, '', 'Vector value', [0, 0, 0], 'VELOCITY', -100, 100)


# BSDF material parameters
    Material.li_bsdf_direc = EnumProperty(items = [('+b', 'Backwards', 'Backwards BSDF'), ('+f', 'Forwards', 'Forwards BSDF'), ('+b +f', 'Bi-directional', 'Bi-directional BSDF')], name = '', description = 'BSDF direction', default = '+b')
    Material.li_bsdf_tensor = EnumProperty(items = [(' ', 'Klems', 'Uniform Klems sample'), ('-t3', 'Symmentric', 'Symmetric Tensor BSDF'), ('-t4', 'Assymmetric', 'Asymmetric Tensor BSDF')], name = '', description = 'BSDF tensor', default = ' ')
    Material.li_bsdf_res = EnumProperty(items = [('1', '2x2', '2x2 sampling resolution'), ('2', '4x4', '4x4 sampling resolution'), ('3', '8x8', '8x8 sampling resolution'), ('4', '16x16', '16x16 sampling resolution'), ('5', '32x32', '32x32 sampling resolution'), ('6', '64x64', '64x64 sampling resolution'), ('7', '128x128', '128x128 sampling resolution')], name = '', description = 'BSDF resolution', default = '4')
    Material.li_bsdf_tsamp = bpy.props.IntProperty(name = '', description = 'BSDF resolution', min = 1, max = 20, default = 4)
    Material.li_bsdf_ksamp = bpy.props.IntProperty(name = '', description = 'BSDF resolution', min = 1, default = 2000)
    Material.li_bsdf_rcparam = sprop("", "rcontrib parameters", 1024, "")
    Material.li_bsdf_proxy_depth = fprop("", "Depth of proxy geometry", -10, 10, 0)
#    Material.flovi_bmionut = fprop("Value", "nuTilda value", -1000, 1000, 0.0)
#    Material.flovi_bmionut_y = fprop("Y", "Value in the Y-direction", -1000, 1000, 0.0)
#    Material.flovi_bmionut_z = fprop("Z", "Value in the Z-direction", -1000, 1000, 0.0)

# Scene parameters
    Scene.latitude = bpy.props.FloatProperty(name = "Latitude", description = "Site decimal latitude (N is positive)", min = -89.99, max = 89.99, default = 52.0)
    Scene.longitude = bpy.props.FloatProperty(name = "Longitude", description = "Site decimal longitude (E is positive)", min = -180, max = 180, default = 0.0)
    Scene.wind_type = eprop([("0", "Speed", "Wind Speed (m/s)"), ("1", "Direction", "Wind Direction (deg. from North)")], "", "Wind metric", "0")
    Scene.vipath = sprop("VI Path", "Path to files included with the VI-Suite ", 1024, addonpath)
    Scene.suns = EnumProperty(items = [('0', 'Single', 'Single sun'), ('1', 'Monthly', 'Monthly sun for chosen time'), ('2', 'Hourly', 'Hourly sun for chosen date')], name = '', description = 'Sunpath sun type', default = '0', update=sunpath1)
    Scene.sunsstrength = bpy.props.FloatProperty(name = "", description = "Sun strength", min = 0, max = 100, default = 0.1, update=sunpath1)
    Scene.sunssize = bpy.props.FloatProperty(name = "", description = "Sun size", min = 0, max = 1, default = 0.01, update=sunpath1)
    Scene.solday = bpy.props.IntProperty(name = "", description = "Day of year", min = 1, max = 365, default = 1, update=sunpath1)
    Scene.solhour = bpy.props.FloatProperty(name = "", description = "Time of day", subtype='TIME', unit='TIME', min = 0, max = 24, default = 12, update=sunpath1)
    (Scene.hourdisp, Scene.spupdate, Scene.timedisp) = [bprop("", "",0)] * 3
    Scene.li_disp_panel = iprop("Display Panel", "Shows the Display Panel", -1, 2, 0)
    Scene.li_disp_count = iprop("", "", 0, 1000, 0)
    Scene.vi_disp_3d = bprop("VI 3D display", "Boolean for 3D results display",  False)
    Scene.vi_disp_3dlevel = bpy.props.FloatProperty(name = "", description = "Level of 3D result plane extrusion", min = 0, max = 500, default = 0, update = eupdate)
    Scene.ss_disp_panel = iprop("Display Panel", "Shows the Display Panel", -1, 2, 0)
    (Scene.lic_disp_panel, Scene.vi_display, Scene.sp_disp_panel, Scene.wr_disp_panel, Scene.ss_leg_display, Scene.en_disp_panel, Scene.li_compliance, Scene.vi_display_rp, Scene.vi_leg_display,
     Scene.vi_display_sel_only, Scene.vi_display_vis_only) = [bprop("", "", False)] * 11
    Scene.vi_leg_max = bpy.props.FloatProperty(name = "", description = "Legend maximum", min = 0, max = 1000000, default = 1000, update=legupdate)
    Scene.vi_leg_min = bpy.props.FloatProperty(name = "", description = "Legend minimum", min = 0, max = 1000000, default = 0, update=legupdate)
    Scene.vi_scatter_max = bpy.props.FloatProperty(name = "", description = "Scatter maximum", min = 0, max = 1000000, default = 1000, update=legupdate)
    Scene.vi_scatter_min = bpy.props.FloatProperty(name = "", description = "Scatter minimum", min = 0, max = 1000000, default = 0, update=legupdate)
    Scene.vi_leg_scale = EnumProperty(items = [('0', 'Linear', 'Linear scale'), ('1', 'Log', 'Logarithmic scale')], name = "", description = "Legend scale", default = '0', update=legupdate)
    Scene.vi_leg_col = EnumProperty(items = [('rainbow', 'Rainbow', 'Rainbow colour scale'), ('gray', 'Grey', 'Grey colour scale'), ('hot', 'Hot', 'Hot colour scale'),
                                             ('CMRmap', 'CMR', 'CMR colour scale'), ('jet', 'Jet', 'Jet colour scale'), ('plasma', 'Plasma', 'Plasma colour scale'),
                                             ('hsv', 'HSV', 'HSV colour scale'), ('viridis', 'Viridis', 'Viridis colour scale')],
                                            name = "", description = "Legend scale", default = 'rainbow', update=colupdate)
    Scene.vi_res_mod = sprop("", "Result modifier", 1024, "")
    Scene.vi_res_py = bprop("", "Boolean for Python function modification of results",  False)
    Scene.script_file = bpy.props.StringProperty(description="Text file to show")
    Scene.vi_leg_unit = sprop("", "Legend unit", 1024, "")
    Scene.vi_bsdfleg_max = bpy.props.FloatProperty(name = "", description = "Legend maximum", min = 0, max = 1000000, default = 100)
    Scene.vi_bsdfleg_min = bpy.props.FloatProperty(name = "", description = "Legend minimum", min = 0, max = 1000000, default = 0)
    Scene.vi_bsdfleg_scale = EnumProperty(items = [('0', 'Linear', 'Linear scale'), ('1', 'Log', 'Logarithmic scale')], name = "", description = "Legend scale", default = '0')    
    Scene.vi_gridify_rot = fprop("deg", "Rotation around face normal", 0.0, 360, 0.0)
    Scene.vi_gridify_us = fprop("m", "Up direction size", 0.01, 10, 0.6)
    Scene.vi_gridify_as = fprop("m", "Side direction size", 0.01, 10, 0.6)

#    Scene.vi_lbsdf_direc = EnumProperty(items = bsdfdirec, name = "", description = "Legend scale")

    Scene.en_disp = EnumProperty(items = [('0', 'Cylinder', 'Cylinder display'), ('1', 'Box', 'Box display')], name = "", description = "Shape of EnVi result object", default = '0')
    Scene.en_disp_unit = EnumProperty(items = enunits, name = "", description = "Type of EnVi metric display")
    Scene.en_disp_punit = EnumProperty(items = enpunits, name = "", description = "Type of EnVi metric display")
    Scene.en_disp_type = EnumProperty(items = enparametric, name = "", description = "Type of EnVi display")

    Scene.en_frame = iprop("", "EnVi frame", 0, 500, 0)
    Scene.en_temp_max = bpy.props.FloatProperty(name = "Max", description = "Temp maximum", default = 24, update=setcols)
    Scene.en_temp_min = bpy.props.FloatProperty(name = "Min", description = "Temp minimum", default = 18, update=setcols)
    Scene.en_hum_max = bpy.props.FloatProperty(name = "Max", description = "Humidity maximum", default = 100, update=setcols)
    Scene.en_hum_min = bpy.props.FloatProperty(name = "Min", description = "Humidity minimum", default = 0, update=setcols)
    Scene.en_heat_max = bpy.props.FloatProperty(name = "Max", description = "Heating maximum", default = 1000, update=setcols)
    Scene.en_heat_min = bpy.props.FloatProperty(name = "Min", description = "Heating minimum", default = 0, update=setcols)
    Scene.en_hrheat_max = bpy.props.FloatProperty(name = "Max", description = "Heat recovery maximum", default = 1000, update=setcols)
    Scene.en_hrheat_min = bpy.props.FloatProperty(name = "Min", description = "Heat recovery minimum", default = 0, update=setcols)
    Scene.en_aheat_max = bpy.props.FloatProperty(name = "Max", description = "Air heating maximum", default = 1000, update=setcols)
    Scene.en_aheat_min = bpy.props.FloatProperty(name = "Min", description = "Air heating minimum", default = 0, update=setcols)
    Scene.en_heatb_max = bpy.props.FloatProperty(name = "Max", description = "Heat balance maximum", default = 1000, update=setcols)
    Scene.en_heatb_min = bpy.props.FloatProperty(name = "Min", description = "Heat balance minimum", default = 0, update=setcols)
    Scene.en_cool_max = bpy.props.FloatProperty(name = "Max", description = "Cooling maximum", default = 1000, update=setcols)
    Scene.en_cool_min = bpy.props.FloatProperty(name = "Min", description = "Cooling minimum", default = 0, update=setcols)
    Scene.en_acool_max = bpy.props.FloatProperty(name = "Max", description = "Air cooling maximum", default = 1000, update=setcols)
    Scene.en_acool_min = bpy.props.FloatProperty(name = "Min", description = "Air cooling minimum", default = 0, update=setcols)
    Scene.en_co2_max = bpy.props.FloatProperty(name = "Max", description = "CO2 maximum", default = 10000, update=setcols)
    Scene.en_co2_min = bpy.props.FloatProperty(name = "Min", description = "CO2 minimum", default = 0, update=setcols)
    Scene.en_shg_max = bpy.props.FloatProperty(name = "Max", description = "Solar heat gain maximum", min = 0, default = 10000, update=setcols)
    Scene.en_shg_min = bpy.props.FloatProperty(name = "Min", description = "Solar heat gain minimum", min = 0, default = 0, update=setcols)
    Scene.en_ppd_max = bpy.props.FloatProperty(name = "Max", description = "PPD maximum", default = 100, max = 100, min = 1, update=setcols)
    Scene.en_ppd_min = bpy.props.FloatProperty(name = "Min", description = "PPD minimum", default = 0, max = 90, min = 0, update=setcols)
    Scene.en_pmv_max = bpy.props.FloatProperty(name = "Max", description = "PMV maximum", default = 3, max = 10, min = -9, update=setcols)
    Scene.en_pmv_min = bpy.props.FloatProperty(name = "Min", description = "PMV minimum", default = -3, max = 9, min = -10, update=setcols)
    Scene.en_occ_max = bpy.props.FloatProperty(name = "Max", description = "Occupancy maximum", default = 3, min = 1, update=setcols)
    Scene.en_occ_min = bpy.props.FloatProperty(name = "Min", description = "Occupancy minimum", default = 0, min = 0, update=setcols)
    Scene.en_eq_max = bpy.props.FloatProperty(name = "Max", description = "Equipment gains maximum", default = 3000, min = 0, update=setcols)
    Scene.en_eq_min = bpy.props.FloatProperty(name = "Min", description = "Equipment gains minimum", default = 0, min = 0, update=setcols)
    Scene.en_iach_max = bpy.props.FloatProperty(name = "Max", description = "Infiltration (ACH)  maximum", default = 2, min = 0.1, update=setcols)
    Scene.en_iach_min = bpy.props.FloatProperty(name = "Min", description = "Infiltration (ACH) minimum", default = 0, min = 0, update=setcols)
    Scene.en_im3s_max = bpy.props.FloatProperty(name = "Max", description = "Infiltration (m3/s)  maximum", default = 0.05, min = 0.01, update=setcols)
    Scene.en_im3s_min = bpy.props.FloatProperty(name = "Min", description = "Infiltration (m3/s) minimum", default = 0, min = 0, update=setcols)
    Scene.en_maxheat_max = bpy.props.FloatProperty(name = "Max", description = "Maximum heating maximum", default = 1000, max = 10000, min = 0, update=setcols)
    Scene.en_maxheat_min = bpy.props.FloatProperty(name = "Min", description = "Maximum heating minimum", default = 0, max = 10000, min = 0, update=setcols)
    Scene.en_aveheat_max = bpy.props.FloatProperty(name = "Max", description = "Average heating maximum", default = 500, max = 10000, min = 0, update=setcols)
    Scene.en_aveheat_min = bpy.props.FloatProperty(name = "Min", description = "Average heating minimum", default = 0, max = 10000, min = 0, update=setcols)
    Scene.en_minheat_max = bpy.props.FloatProperty(name = "Max", description = "Minimum heating maximum", default = 3, max = 10, min = -9, update=setcols)
    Scene.en_minheat_min = bpy.props.FloatProperty(name = "Min", description = "Minimum heating minimum", default = -3, max = 9, min = -10, update=setcols)
    Scene.en_maxcool_max = bpy.props.FloatProperty(name = "Max", description = "Maximum cooling maximum", default = 1000, max = 10000, min = 0, update=setcols)
    Scene.en_maxcool_min = bpy.props.FloatProperty(name = "Min", description = "Maximum cooling minimum", default = 0, max = 10000, min = 0, update=setcols)
    Scene.en_avecool_max = bpy.props.FloatProperty(name = "Max", description = "Average cooling maximum", default = 500, max = 10000, min = 0, update=setcols)
    Scene.en_avecool_min = bpy.props.FloatProperty(name = "Min", description = "Average cooling minimum", default = 0, max = 10000, min = 0, update=setcols)
    Scene.en_mincool_max = bpy.props.FloatProperty(name = "Max", description = "Minimum cooling maximum", default = 3, max = 10, min = -9, update=setcols)
    Scene.en_mincool_min = bpy.props.FloatProperty(name = "Min", description = "Minimum cooling minimum", default = -3, max = 9, min = -10, update=setcols)
    Scene.en_maxtemp_max = bpy.props.FloatProperty(name = "Max", description = "Maximum temperature maximum", default = 25, max = 100, min = -100, update=setcols)
    Scene.en_maxtemp_min = bpy.props.FloatProperty(name = "Min", description = "Maximum temperature minimum", default = 18, max = 50, min = -50, update=setcols)
    Scene.en_avetemp_max = bpy.props.FloatProperty(name = "Max", description = "Average temperature maximum", default = 20, max = 40, min = 0, update=setcols)
    Scene.en_avetemp_min = bpy.props.FloatProperty(name = "Min", description = "Average temperature minimum", default = 20, max = 30, min = 5, update=setcols)
    Scene.en_mintemp_max = bpy.props.FloatProperty(name = "Max", description = "Minimum temperature maximum", default = 15, max = 30, min = 0, update=setcols)
    Scene.en_mintemp_min = bpy.props.FloatProperty(name = "Min", description = "Minimum temperature minimum", default = 5, max = 30, min = 0, update=setcols)
    Scene.en_tothkwhm2_max = bpy.props.FloatProperty(name = "Max", description = "Total heating per m2 floor area maximum", default = 100, min = 1, update=setcols)
    Scene.en_tothkwhm2_min = bpy.props.FloatProperty(name = "Min", description = "Total heating per m2 floor area minimum", default = 5, min = 0, update=setcols)
    Scene.en_tothkwh_max = bpy.props.FloatProperty(name = "Max", description = "Total heating maximum", default = 100, min = 1, update=setcols)
    Scene.en_tothkwh_min = bpy.props.FloatProperty(name = "Min", description = "Total heating minimum", default = 5, min = 0, update=setcols)
    Scene.en_totckwhm2_max = bpy.props.FloatProperty(name = "Max", description = "Total cooling per m2 floor area maximum", default = 100, min = 1, update=setcols)
    Scene.en_totckwhm2_min = bpy.props.FloatProperty(name = "Min", description = "Total cooling per m2 floor area minimum", default = 5, min = 0, update=setcols)
    Scene.en_totckwh_max = bpy.props.FloatProperty(name = "Max", description = "Total cooling maximum", default = 100, min = 1, update=setcols)
    Scene.en_totckwh_min = bpy.props.FloatProperty(name = "Min", description = "Total cooling minimum", default = 5, min = 0, update=setcols)
    Scene.en_maxshg_max = bpy.props.FloatProperty(name = "Max", description = "Maximum solar heat gain maximum", default = 1000, min = 1, update=setcols)
    Scene.en_maxshg_min = bpy.props.FloatProperty(name = "Min", description = "Maximum solar heat gain minimum", default = 0, min = 0, update=setcols)
    Scene.en_aveshg_max = bpy.props.FloatProperty(name = "Max", description = "Average solar heat gain maximum", default = 500, min = 1, update=setcols)
    Scene.en_aveshg_min = bpy.props.FloatProperty(name = "Min", description = "Average solar heat gain minimum", default = 0, min = 0, update=setcols)
    Scene.en_minshg_max = bpy.props.FloatProperty(name = "Max", description = "Minimum solar heat gain maximum", default = 100, min = 1, update=setcols)
    Scene.en_minshg_min = bpy.props.FloatProperty(name = "Min", description = "Minimum solar heat gain minimum", default = 0, min = 0, update=setcols)
    Scene.en_totshgkwhm2_max = bpy.props.FloatProperty(name = "Max", description = "Total solar heat gain per m2 floor area maximum", default = 100, min = 1, update=setcols)
    Scene.en_totshgkwhm2_min = bpy.props.FloatProperty(name = "Min", description = "Total solar heat gain per m2 floor area minimum", default = 5, min = 0, update=setcols)
    Scene.en_totshgkwh_max = bpy.props.FloatProperty(name = "Max", description = "Total solar heat gain maximum", default = 100, min = 1, update=setcols)
    Scene.en_totshgkwh_min = bpy.props.FloatProperty(name = "Min", description = "Total solar heat gain minimum", default = 5, min = 0, update=setcols)
    Scene.bar_min = bpy.props.FloatProperty(name = "Min", description = "Bar graph minimum", default = 0, update=setcols)
    Scene.bar_max = bpy.props.FloatProperty(name = "Max", description = "Bar graph maximum", default = 100, update=setcols)
    Scene.vi_display_rp_fs = iprop("", "Point result font size", 4, 24, 24)
    Scene.vi_display_rp_fc = fvprop(4, "", "Font colour", [0.0, 0.0, 0.0, 1.0], 'COLOR', 0, 1)
    Scene.vi_display_rp_sh = bprop("", "Toggle for font shadow display",  False)
    Scene.vi_display_rp_fsh = fvprop(4, "", "Font shadow", [0.0, 0.0, 0.0, 1.0], 'COLOR', 0, 1)
    Scene.vi_display_rp_off = fprop("", "Surface offset for number display", 0, 5, 0.001)
    Scene.vi_disp_trans = bpy.props.FloatProperty(name = "", description = "Sensing material transparency", min = 0, max = 1, default = 1, update = tupdate)
    Scene.vi_disp_wire = bpy.props.BoolProperty(name = "", description = "Draw wire frame", default = 0, update=wupdate)
    Scene.vi_disp_mat = bpy.props.BoolProperty(name = "", description = "Turn on/off result material emission", default = 0, update=colupdate)
    Scene.vi_disp_ems = bpy.props.FloatProperty(name = "", description = "Emissive strength", default = 1, min = 0, update=colupdate)
    Scene.li_disp_sv = EnumProperty(items = [("0", "Daylight Factor", "Display Daylight factor"),("1", "Sky view", "Display the Sky View")], name = "", description = "Compliance data type", default = "0", update = liviresupdate)
    Scene.li_disp_sda = EnumProperty(items = [("0", "sDA (%)", "Display spatial Daylight Autonomy"), ("1", "ASE (hrs)", "Display the Annual Solar Exposure")], name = "", description = "Compliance data type", default = "0", update = liviresupdate)
    Scene.li_disp_wr = EnumProperty(items = [("0", "Wind Speed", "Wind speed (m/s)"),("1", "Wind Direction", "Wind direction (deg from North)")], name = "", description = "Compliance data type", default = "0", update = liviresupdate)
 #   Scene.li_disp_lh = EnumProperty(items = [("0", "Mluxhours", "Display mega luxhours"), ("1", "Visible Irradiance", "Display visible irradiance"), ("1", "Full Irradiance", "Display full irradiance")], name = "", description = "Exposure data type", default = "0", update = liviresupdate)
#    Scene.li_projname = sprop("", "Name of the building project", 1024, '')
#    Scene.li_assorg = sprop("", "Name of the assessing organisation", 1024, '')
#    Scene.li_assind = sprop("", "Name of the assessing individual", 1024, '')
#    Scene.li_jobno = sprop("", "Project job number", 1024, '')
    Scene.li_disp_basic = EnumProperty(items = [("0", "Illuminance", "Display Illuminance values"), ("1", "Visible Irradiance", "Display Irradiance values"), ("2", "Full Irradiance", "Display Irradiance values"), ("3", "DF", "Display Daylight factor values")], name = "", description = "Basic metric selection", default = "0", update = liviresupdate)
    Scene.li_disp_da = EnumProperty(items = [("0", "DA", "Daylight Autonomy"), ("1", "sDA", "Spatial Daylight Autonomy"), ("2", "UDILow", "Spatial Daylight Autonomy"), ("3", "UDISup", "Spatial Daylight Autonomy"),
                                             ("4", "UDIAuto", "Spatial Daylight Autonomy"), ("5", "UDIHigh", "Spatial Daylight Autonomy"), ("6", "ASE", "Annual sunlight exposure"), ("7", "Max lux", "Maximum lux level"),
                                             ("8", "Avg Lux", "Average lux level"), ("9", "Min lux", "Minimum lux level")], name = "", description = "Result selection", default = "0", update = liviresupdate)
    Scene.li_disp_exp = EnumProperty(items = [("0", "LuxHours", "Display LuhHours values"), ("1", "Full Irradiance", "Display full spectrum radiation exposure values"), ("2", "Visible Irradiance", "Display visible spectrum radiation exposure values"),
                                              ("3", "Full Irradiance Density", "Display full spectrum radiation exposure values"), ("4", "Visible Irradiance Density", "Display visible spectrum radiation exposure values")], name = "", description = "Result selection", default = "0", update = liviresupdate)
    Scene.li_disp_irrad = EnumProperty(items = [("0", "kWh", "Display kWh values"), ("1", "kWh/m2", "Display kWh/m2 values")], name = "", description = "Result selection", default = "0", update = liviresupdate)
    (Scene.resaa_disp, Scene.resaws_disp, Scene.resawd_disp, Scene.resah_disp, Scene.resas_disp, Scene.reszt_disp, Scene.reszh_disp, Scene.reszhw_disp, Scene.reszcw_disp, Scene.reszsg_disp, Scene.reszppd_disp,
     Scene.reszpmv_disp, Scene.resvls_disp, Scene.resvmh_disp, Scene.resim_disp, Scene.resiach_disp, Scene.reszco_disp, Scene.resihl_disp, Scene.reszlf_disp, Scene.reszof_disp, Scene.resmrt_disp,
     Scene.resocc_disp, Scene.resh_disp, Scene.resfhb_disp, Scene.reszahw_disp, Scene.reszacw_disp, Scene.reshrhw_disp, Scene.restcvf_disp, Scene.restcmf_disp, Scene.restcot_disp, Scene.restchl_disp,
     Scene.restchg_disp, Scene.restcv_disp, Scene.restcm_disp, Scene.resldp_disp, Scene.resoeg_disp, Scene.respve_disp, Scene.respvw_disp, Scene.respveff_disp, Scene.respvt_disp)  = resnameunits()

    (Scene.resazmaxt_disp, Scene.resazmint_disp, Scene.resazavet_disp,
     Scene.resazmaxhw_disp, Scene.resazminhw_disp, Scene.resazavehw_disp,
     Scene.resazth_disp, Scene.resazthm_disp,
     Scene.resazmaxcw_disp, Scene.resazmincw_disp, Scene.resazavecw_disp,
     Scene.resaztc_disp, Scene.resaztcm_disp,
     Scene.resazmaxco_disp, Scene.resazaveco_disp, Scene.resazminco_disp,
     Scene.resazlmaxf_disp, Scene.resazlminf_disp, Scene.resazlavef_disp,
     Scene.resazmaxshg_disp, Scene.resazminshg_disp, Scene.resazaveshg_disp,
     Scene.resaztshg_disp, Scene.resaztshgm_disp)  = aresnameunits()
    Scene.envi_flink = bprop("", "Associate flow results with the nearest object", False)

    nodeitems_utils.register_node_categories("Vi Nodes", vinode_categories)
    nodeitems_utils.register_node_categories("EnVi Nodes", envinode_categories)
    nodeitems_utils.register_node_categories("EnVi Mat Nodes", envimatnode_categories)

    if update_chart_node not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(update_chart_node)

    if display_off not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(display_off)

    if mesh_index not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(mesh_index)

    if update_dir not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(update_dir)

    path_update()

def unregister():
    bpy.utils.unregister_module(__name__)
    nodeitems_utils.unregister_node_categories("Vi Nodes")
    nodeitems_utils.unregister_node_categories("EnVi Nodes")
    nodeitems_utils.unregister_node_categories("EnVi Mat Nodes")

    if update_chart_node in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(update_chart_node)

    if display_off in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(display_off)

    if mesh_index in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(mesh_index)

    if update_dir in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(update_dir)
#if __name__ == "__main__":
#    register()
