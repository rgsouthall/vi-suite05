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


import bpy, glob, os, inspect, datetime, shutil, time
from nodeitems_utils import NodeCategory, NodeItem
from .vi_func import objvol, socklink, uvsocklink, newrow, epwlatilongi, nodeid, nodeinputs, remlink, rettimes, sockhide, selobj, cbdmhdr, cbdmmtx
from .vi_func import hdrsky, nodecolour, facearea, retelaarea, iprop, bprop, eprop, fprop, sunposlivi, retdates
from .envi_func import retrmenus, resnameunits, enresprops, epentry, epschedwrite
from .livi_export import sunexport, skyexport, hdrexport
from .envi_mat import retuval

class ViNetwork(bpy.types.NodeTree):
    '''A node tree for VI-Suite analysis.'''
    bl_idname = 'ViN'
    bl_label = 'Vi Network'
    bl_icon = 'LAMP_SUN'
    viparams = {}
        
class ViNodes:
    @classmethod
    def poll(cls, ntree):
        return ntree.bl_idname == 'ViN'

class ViLoc(bpy.types.Node, ViNodes):
    '''Node describing a geographical location manually or with an EPW file'''
    bl_idname = 'ViLoc'
    bl_label = 'VI Location'
    bl_icon = 'FORCE_WIND'

    def updatelatlong(self, context):
        context.space_data.edit_tree == ''
#        print(bpy.types.NodeTree.get_from_context(context))
        scene = context.scene
        nodecolour(self, self.ready())
        reslists = []

        if self.loc == '1':
            entries = []
            addonfolder = os.path.basename(os.path.dirname(os.path.abspath(__file__)))
            vi_prefs = bpy.context.user_preferences.addons['{}'.format(addonfolder)].preferences
        
            if vi_prefs and os.path.isdir(bpy.path.abspath(vi_prefs.epweath)):
                epwpath = bpy.path.abspath(vi_prefs.epweath)
            else:
                epwpath = os.path.dirname(os.path.abspath(__file__)) + '/EPFiles/Weather/'
    
            for wfile in glob.glob(epwpath+"/*.epw"):
                with open(wfile, 'r') as wf:
                    for wfl in wf.readlines():
                        if wfl.split(',')[0].upper() == 'LOCATION':
                            entries.append((wfile, '{} - {}'.format(wfl.split(',')[3], wfl.split(',')[1]), 'Weather Location'))
                            break
            self['entries'] = entries if entries else [('None', 'None', 'None')]
            
            if self.weather:            
                with open(self.weather, 'r') as epwfile:                
                    self['frames'] = ['0']
                    epwlines = epwfile.readlines()[8:]
                    epwcolumns = list(zip(*[epwline.split(',') for epwline in epwlines]))
                    self['year'] = 2015 if len(epwlines) == 8760 else 2016
                    times = ('Month', 'Day', 'Hour', 'DOS')
                    
                    for t, ti in enumerate([' '.join(epwcolumns[c]) for c in range(1,4)] + [' '.join(['{}'.format(int(d/24) + 1) for d in range(len(epwlines))])]):
                        reslists.append(['0', 'Time', '', times[t], ti])
                        
                    for c in {"Temperature ("+ u'\u00b0'+"C)": 6, 'Humidity (%)': 8, "Direct Solar (W/m"+u'\u00b2'+")": 14, "Diffuse Solar (W/m"+u'\u00b2'+")": 15,
                              'Wind Direction (deg)': 20, 'Wind Speed (m/s)': 21}.items():
                        reslists.append(['0', 'Climate', '', c[0], ' '.join([cdata for cdata in list(epwcolumns[c[1]])])])
    
                    self.outputs['Location out']['epwtext'] = epwfile.read()
                    self.outputs['Location out']['valid'] = ['Location', 'Vi Results']
            else:
                self.outputs['Location out']['epwtext'] = ''
                self.outputs['Location out']['valid'] = ['Location']

        socklink(self.outputs['Location out'], self['nodeid'].split('@')[1])
        self['reslists'] = reslists
        (scene.latitude, scene.longitude) = epwlatilongi(context.scene, self) if self.loc == '1' and self.weather != 'None' else (scene.latitude, scene.longitude)

        for node in [l.to_node for l in self.outputs['Location out'].links]:
            node.update()
                
    def retentries(self, context):
        try:
            return [tuple(e) for e in self['entries']]
        except:
            return [('None', 'None','None' )]
                  
    weather = bpy.props.EnumProperty(name = 'Weather file', items=retentries, update=updatelatlong)
    loc = bpy.props.EnumProperty(items = [("0", "Manual", "Manual location"), ("1", "EPW ", "Get location from EPW file")], name = "", description = "Location", default = "0", update = updatelatlong)
    maxws = bpy.props.FloatProperty(name="", description="Max wind speed", min=0, max=90, default=0)
    minws = bpy.props.FloatProperty(name="", description="Min wind speed", min=0, max=90, default=0)
    avws = bpy.props.FloatProperty(name="", description="Average wind speed", min=0, max=90, default=0)
    dsdoy = bpy.props.IntProperty(name="", description="", min=1, max=365, default=1)
    dedoy = bpy.props.IntProperty(name="", description="", min=1, max=365, default=365)

    def init(self, context):
        self['nodeid'] = nodeid(self)        
        bpy.data.node_groups[nodeid(self).split('@')[1]].use_fake_user = True
        self.outputs.new('ViLoc', 'Location out')
        self['year'] = 2015
        self['entries'] = [('None', 'None', 'None')] 

    def update(self):
        socklink(self.outputs['Location out'], self['nodeid'].split('@')[1])
        nodecolour(self, self.ready())
        
    def draw_buttons(self, context, layout):
        row = layout.row()
        row.label(text = 'Source:')
        row.prop(self, "loc")
        if self.loc == "1":
            row = layout.row()
            row.prop(self, "weather")
        else:
            row = layout.row()
            row.prop(context.scene, "latitude")
            row = layout.row()
            row.prop(context.scene, "longitude")
            
    def ready(self):
        if self.loc == '1' and not self.weather:
            return 1
        if any([link.to_node.bl_label in ('LiVi CBDM', 'EnVi Export') and self.loc != "1" for link in self.outputs['Location out'].links]):
            return 1
        return 0
        

class ViGExLiNode(bpy.types.Node, ViNodes):
    '''Node describing a LiVi geometry export node'''
    bl_idname = 'ViGExLiNode'
    bl_label = 'LiVi Geometry'
    bl_icon = 'LAMP'

    def nodeupdate(self, context):
        nodecolour(self, self['exportstate'] != [str(x) for x in (self.animated, self.startframe, self.endframe, self.cpoint, self.offset)])

    cpoint = bpy.props.EnumProperty(items=[("0", "Faces", "Export faces for calculation points"),("1", "Vertices", "Export vertices for calculation points"), ],
            name="", description="Specify the calculation point geometry", default="0", update = nodeupdate)
    offset = bpy.props.FloatProperty(name="", description="Calc point offset", min = 0.001, max = 1, default = 0.01, update = nodeupdate)
    animated = bpy.props.BoolProperty(name="", description="Animated analysis", default = 0, update = nodeupdate)
    startframe = bpy.props.IntProperty(name="", description="Start frame for animation", min = 0, default = 0, update = nodeupdate)
    endframe = bpy.props.IntProperty(name="", description="End frame for animation", min = 0, default = 0, update = nodeupdate)
    
    def init(self, context):
        self['exportstate'] = ''
        self['nodeid'] = nodeid(self)
        self.outputs.new('ViLiG', 'Geometry out')
        nodecolour(self, 1)

    def draw_buttons(self, context, layout):
        newrow(layout, 'Animated:', self, 'animated')
        if self.animated:
            row = layout.row()
            row.label(text = 'Frames:')
            col = row.column()
            subrow = col.row(align=True)
            subrow.prop(self, 'startframe')
            subrow.prop(self, 'endframe')

        newrow(layout, 'Result point:', self, 'cpoint')
        newrow(layout, 'Offset:', self, 'offset')
        row = layout.row()
        row.operator("node.ligexport", text = "Export").nodeid = self['nodeid']

    def update(self):
        socklink(self.outputs['Geometry out'], self['nodeid'].split('@')[1])

    def preexport(self, scene):
        self['Text'] = {}
        self['Options'] = {'offset': self.offset, 'fs': (scene.frame_current, self.startframe)[self.animated], 'fe': (scene.frame_current, self.endframe)[self.animated], 'cp': self.cpoint, 'anim': self.animated}
        
    def postexport(self, scene):
        bpy.data.node_groups[self['nodeid'].split('@')[1]].use_fake_user = 1
        self['exportstate'] = [str(x) for x in (self.animated, self.startframe, self.endframe, self.cpoint, self.offset)]
        nodecolour(self, 0)

class LiViNode(bpy.types.Node, ViNodes):
    '''Node for creating a LiVi analysis'''
    bl_idname = 'LiViNode'
    bl_label = 'LiVi Context'
    bl_icon = 'LAMP'

    def nodeupdate(self, context):
        scene = context.scene
        nodecolour(self, self['exportstate'] != [str(x) for x in (self.contextmenu, self.banalysismenu, self.canalysismenu, self.cbanalysismenu, 
                   self.animated, self.skymenu, self.shour, self.sdoy, self.startmonth, self.endmonth, self.damin, self.dasupp, self.dalux, self.daauto,
                   self.ehour, self.edoy, self.interval, self.hdr, self.hdrname, self.skyname, self.resname, self.turb, self.mtxname, self.cbdm_start_hour,
                   self.cbdm_end_hour, self.bambuildmenu)])
        if self.edoy < self.sdoy:
            self.edoy = self.sdoy
        if self.edoy == self.sdoy:
            if self.ehour < self.shour:
                self.ehour = self.shour
        
        self['skynum'] = int(self.skymenu)         
        suns = [ob for ob in scene.objects if ob.type == 'LAMP' and ob.data.type == 'SUN'] 
                
        if self.contextmenu == 'Basic' and self['skynum'] < 2:
            starttime = datetime.datetime(2015, 1, 1, int(self.shour), int((self.shour - int(self.shour))*60)) + datetime.timedelta(self.sdoy - 1) if self['skynum'] < 3 else datetime.datetime(2013, 1, 1, 12)                                       
            self['endframe'] = self.startframe + int(((24 * (self.edoy - self.sdoy) + self.ehour - self.shour)/self.interval)) if self.animated else [scene.frame_current]
            frames = range(self.startframe, self['endframe'] + 1) if self.animated else [scene.frame_current]
            scene.frame_start, scene.frame_end = self.startframe, frames[-1]
            if suns:
                sun = suns[0]
                sun['VIType'] = 'Sun'
                [scene.objects.unlink(o) for o in suns[1:]]
            else:
                bpy.ops.object.lamp_add(type='SUN')
                sun = bpy.context.object
                sun['VIType'] = 'Sun'

            if self.inputs['Location in'].links and suns:
                sunposlivi(scene, self, frames, sun, starttime)
        else:
            for so in suns:
                selobj(scene, so)
                bpy.ops.object.delete()
                
                                
    banalysistype = [('0', "Illu/Irrad/DF", "Illumninance/Irradiance/Daylight Factor Calculation"), ('1', "Glare", "Glare Calculation")]
    skylist = [("0", "Sunny", "CIE Sunny Sky description"), ("1", "Partly Coudy", "CIE Sunny Sky description"),
               ("2", "Coudy", "CIE Partly Cloudy Sky description"), ("3", "DF Sky", "Daylight Factor Sky description"),
               ("4", "HDR Sky", "HDR file sky"), ("5", "Radiance Sky", "Radiance file sky"), ("6", "None", "No Sky")]

    contexttype = [('Basic', "Basic", "Basic analysis"), ('Compliance', "Compliance", "Compliance analysis"), ('CBDM', "CBDM", "Climate based daylight modelling")]
    contextmenu = bpy.props.EnumProperty(name="", description="Contexttype type", items=contexttype, default = 'Basic', update = nodeupdate)
    animated = bpy.props.BoolProperty(name="", description="Animated sky", default=False, update = nodeupdate)
    offset = bpy.props.FloatProperty(name="", description="Calc point offset", min=0.001, max=1, default=0.01, update = nodeupdate)
    banalysismenu = bpy.props.EnumProperty(name="", description="Type of lighting analysis", items = banalysistype, default = '0', update = nodeupdate)
    skymenu = bpy.props.EnumProperty(name="", items=skylist, description="Specify the type of sky for the simulation", default="0", update = nodeupdate)
    shour = bpy.props.FloatProperty(name="", description="Hour of simulation", min=0, max=23.99, default=12, subtype='TIME', unit='TIME', update = nodeupdate)
    sdoy = bpy.props.IntProperty(name="", description="Day of simulation", min=1, max=365, default=1, update = nodeupdate)
    ehour = bpy.props.FloatProperty(name="", description="Hour of simulation", min=0, max=23.99, default=12, subtype='TIME', unit='TIME', update = nodeupdate)
    edoy = bpy.props.IntProperty(name="", description="Day of simulation", min=1, max=365, default=1, update = nodeupdate)
    interval = bpy.props.FloatProperty(name="", description="Site Latitude", min=1/60, max=24, default=1, update = nodeupdate)
    hdr = bpy.props.BoolProperty(name="", description="Export HDR panoramas", default=False, update = nodeupdate)
    skyname = bpy.props.StringProperty(name="", description="Name of the Radiance sky file", default="", update = nodeupdate)
    resname = bpy.props.StringProperty()
    turb = bpy.props.FloatProperty(name="", description="Sky Turbidity", min=1.0, max=5.0, default=2.75, update = nodeupdate)
    canalysistype = [('0', "BREEAM", "BREEAM HEA1 calculation"), ('1', "CfSH", "Code for Sustainable Homes calculation"), ('2', "Green Star", "Green Star Calculation"), ('3', "LEED", "LEED v4 Daylight calculation")]
    bambuildtype = [('0', "School", "School lighting standard"), ('1', "Higher Education", "Higher education lighting standard"), ('2', "Healthcare", "Healthcare lighting standard"), ('3', "Residential", "Residential lighting standard"), ('4', "Retail", "Retail lighting standard"), ('5', "Office & other", "Office and other space lighting standard")]
    lebuildtype = [('0', "Office/Education/Commercial", "Office/Education/Commercial lighting standard"), ('1', "Healthcare", "Healthcare lighting standard")]
    canalysismenu = bpy.props.EnumProperty(name="", description="Type of analysis", items = canalysistype, default = '0', update = nodeupdate)
    bambuildmenu = bpy.props.EnumProperty(name="", description="Type of building", items=bambuildtype, default = '0', update = nodeupdate)
    lebuildmenu = bpy.props.EnumProperty(name="", description="Type of building", items=lebuildtype, default = '0', update = nodeupdate)
    cusacc = bpy.props.StringProperty(name="", description="Custom Radiance simulation parameters", default="", update = nodeupdate)
    buildstorey = bpy.props.EnumProperty(items=[("0", "Single", "Single storey building"),("1", "Multi", "Multi-storey building")], name="", description="Building storeys", default="0", update = nodeupdate)
    cbanalysistype = [('0', "Exposure", "LuxHours/Irradiance Exposure Calculation"), ('1', "Hourly irradiance", "Irradiance for each simulation time step"), ('2', "DA/UDI/SDA/ASE", "Useful Daylight Illuminance")]
    cbanalysismenu = bpy.props.EnumProperty(name="", description="Type of lighting analysis", items = cbanalysistype, default = '0', update = nodeupdate)
#    leanalysistype = [('0', "Light Exposure", "LuxHours Calculation"), ('1', "Radiation Exposure", "kWh/m"+ u'\u00b2' + " Calculation"), ('2', "Daylight Autonomy", "DA (%) Calculation")]
    sourcetype = [('0', "EPW", "EnergyPlus weather file"), ('1', "HDR", "HDR sky file")]
    sourcetype2 = [('0', "EPW", "EnergyPlus weather file"), ('1', "VEC", "Generated vector file")]
    sourcemenu = bpy.props.EnumProperty(name="", description="Source type", items=sourcetype, default = '0', update = nodeupdate)
    sourcemenu2 = bpy.props.EnumProperty(name="", description="Source type", items=sourcetype2, default = '0', update = nodeupdate)
    hdrname = bpy.props.StringProperty(name="", description="Name of the composite HDR sky file", default="", update = nodeupdate)
    hdrmap = bpy.props.EnumProperty(items=[("0", "Polar", "Polar ot LatLong HDR mapping"),("1", "Angular", "Light probe or angular mapping")], name="", description="Type of HDR panorama mapping", default="0", update = nodeupdate)
    hdrangle = bpy.props.FloatProperty(name="", description="HDR rotation (deg)", min=0, max=360, default=0, update = nodeupdate)
    hdrradius = bpy.props.FloatProperty(name="", description="HDR radius (m)", min=0, max=5000, default=1000, update = nodeupdate)
    mtxname = bpy.props.StringProperty(name="", description="Name of the calculated vector sky file", default="", update = nodeupdate)
    weekdays = bpy.props.BoolProperty(name = '', default = False, update = nodeupdate)
    cbdm_start_hour =  bpy.props.IntProperty(name = '', default = 8, min = 1, max = 24, update = nodeupdate)
    cbdm_end_hour =  bpy.props.IntProperty(name = '', default = 20, min = 1, max = 24, update = nodeupdate)
    dalux =  bpy.props.IntProperty(name = '', default = 300, min = 1, max = 2000, update = nodeupdate)
    damin = bpy.props.IntProperty(name = '', default = 100, min = 1, max = 2000, update = nodeupdate)
    dasupp = bpy.props.IntProperty(name = '', default = 300, min = 1, max = 2000, update = nodeupdate)
    daauto = bpy.props.IntProperty(name = '', default = 3000, min = 1, max = 5000, update = nodeupdate)
    sdamin = bpy.props.IntProperty(name = '', default = 300, min = 1, max = 2000, update = nodeupdate) 
    asemax = bpy.props.IntProperty(name = '', default = 1000, min = 1, max = 2000, update = nodeupdate)
    startmonth = bpy.props.IntProperty(name = '', default = 1, min = 1, max = 12, description = 'Start Month', update = nodeupdate)
    endmonth = bpy.props.IntProperty(name = '', default = 12, min = 1, max = 12, description = 'End Month', update = nodeupdate)
    startframe = bpy.props.IntProperty(name = '', default = 0, min = 0, description = 'Start Frame', update = nodeupdate)

    def init(self, context):
        self['exportstate'], self['skynum'] = '', 0
        self['nodeid'] = nodeid(self)
        self['whitesky'] = "void glow sky_glow \n0 \n0 \n4 1 1 1 0 \nsky_glow source sky \n0 \n0 \n4 0 0 1 180 \nvoid glow ground_glow \n0 \n0 \n4 1 1 1 0 \nground_glow source ground \n0 \n0 \n4 0 0 -1 180\n\n"
        self.outputs.new('ViLiC', 'Context out')
        self.inputs.new('ViLoc', 'Location in')
        nodecolour(self, 1)

    def draw_buttons(self, context, layout):
        newrow(layout, 'Context:', self, 'contextmenu')
        (sdate, edate) = retdates(self.sdoy, self.edoy, 2015)
        if self.contextmenu == 'Basic':            
            newrow(layout, "Standard:", self, 'banalysismenu')
            newrow(layout, "Sky type:", self, 'skymenu')
            if self.skymenu in ('0', '1', '2'):
                newrow(layout, "Start hour:", self, 'shour')
                newrow(layout, 'Start day {}/{}:'.format(sdate.day, sdate.month), self, "sdoy")
                newrow(layout, "Animation;", self, 'animated')
                if self.animated:
                    newrow(layout, "Start frame:", self, 'startframe')
                    row = layout.row()
                    row.label(text = 'End frame:')
                    row.label(text = '{}'.format(self['endframe']))
                    newrow(layout, "End hour:", self, 'ehour')
                    newrow(layout, 'End day {}/{}:'.format(edate.day, edate.month), self, "edoy")
                    newrow(layout, "Interval (hours):", self, 'interval')
                newrow(layout, "Turbidity", self, 'turb')
            elif self.skymenu == '4':
                row = layout.row()
                row.label("HDR file:")
                row.operator('node.hdrselect', text = 'HDR select').nodeid = self['nodeid']
                row = layout.row()
                row.prop(self, 'hdrname')
                newrow(layout, "HDR format:", self, 'hdrmap')
                newrow(layout, "HDR rotation:", self, 'hdrangle')
                newrow(layout, "HDR radius:", self, 'hdrradius')
            elif self.skymenu == '5':
                row = layout.row()
                row.label("Radiance file:")
                row.operator('node.skyselect', text = 'Sky select').nodeid = self['nodeid']
                row = layout.row()
                row.prop(self, 'skyname')
            row = layout.row()

            if self.skymenu not in ('4', '6'):
                newrow(layout, 'HDR:', self, 'hdr')

        elif self.contextmenu == 'Compliance':
            newrow(layout, "Standard:", self, 'canalysismenu')
            if self.canalysismenu == '0':
                newrow(layout, "Building type:", self, 'bambuildmenu')
                newrow(layout, "Storeys:", self, 'buildstorey')
            if self.canalysismenu == '2':
                newrow(layout, "Building type:", self, 'bambuildmenu')
            if self.canalysismenu == '3':
                newrow(layout, "Building type:", self, 'lebuildmenu')
                newrow(layout, 'Weekdays only:', self, 'weekdays')
                newrow(layout, 'Start hour:', self, 'cbdm_start_hour')
                newrow(layout, 'End hour:', self, 'cbdm_end_hour')
                newrow(layout, 'Source file:', self, 'sourcemenu2') 
                if self.sourcemenu2 == '1':
                    row = layout.row()
                    row.operator('node.mtxselect', text = 'Select MTX').nodeid = self['nodeid']
                    row = layout.row()
                    row.prop(self, 'mtxname')
            newrow(layout, 'HDR:', self, 'hdr')
                
        elif self.contextmenu == 'CBDM':
            newrow(layout, 'Type:', self, 'cbanalysismenu')
            newrow(layout, 'Start day {}/{}:'.format(sdate.day, sdate.month), self, "sdoy")
            newrow(layout, 'End day {}/{}:'.format(edate.day, edate.month), self, "edoy")
            newrow(layout, 'Weekdays only:', self, 'weekdays')
            newrow(layout, 'Start hour:', self, 'cbdm_start_hour')
            newrow(layout, 'End hour:', self, 'cbdm_end_hour')
            row = layout.row()
            row.label("--")
            if self.cbanalysismenu == '2':
                newrow(layout, '(s)DA Min lux:', self, 'dalux')
                row = layout.row()
                row.label("--")
                newrow(layout, 'UDI Fell short (Max):', self, 'damin')
                newrow(layout, 'UDI Supplementry (Max):', self, 'dasupp')
                newrow(layout, 'UDI Autonomous (Max):', self, 'daauto')
                row = layout.row()
                row.label("--")
                newrow(layout, 'ASE Lux level:', self, 'asemax')
                   
            if self.cbanalysismenu == '0':
                newrow(layout, 'Source file:', self, 'sourcemenu')
            else:
                newrow(layout, 'Source file:', self, 'sourcemenu2')
            row = layout.row()
            if self.sourcemenu2 == '1' and self.cbanalysismenu in ('1', '2'):
                row.operator('node.mtxselect', text = 'Select MTX').nodeid = self['nodeid']
                row = layout.row()
                row.prop(self, 'mtxname')
            if self.sourcemenu == '1' and self.cbanalysismenu == '0':
                row.operator('node.hdrselect', text = 'Select HDR').nodeid = self['nodeid']
                row = layout.row()
                row.prop(self, 'hdrname')
            else:
                newrow(layout, 'HDR:', self, 'hdr')
        
        if self.contextmenu == 'Basic':
            if int(self.skymenu) > 2 or (int(self.skymenu) < 3 and self.inputs['Location in'].links):
                row = layout.row()
                row.operator("node.liexport", text = "Export").nodeid = self['nodeid']
        elif self.contextmenu == 'Compliance' and self.canalysismenu != '3':
            row = layout.row()
            row.operator("node.liexport", text = "Export").nodeid = self['nodeid']
        elif (self.contextmenu == 'CBDM' and self.cbanalysismenu == '0' and self.sourcemenu2 == '1') or \
            (self.contextmenu == 'CBDM' and self.cbanalysismenu != '0' and self.sourcemenu == '1'):         
            row = layout.row()
            row.operator("node.liexport", text = "Export").nodeid = self['nodeid']   
        elif self.inputs['Location in'].links and self.inputs['Location in'].links[0].from_node.loc == '1' and self.inputs['Location in'].links[0].from_node.weather != 'None':
            row = layout.row()
            row.operator("node.liexport", text = "Export").nodeid = self['nodeid'] 

    def update(self):
        socklink(self.outputs['Context out'], self['nodeid'].split('@')[1])
        if self.inputs.get('Location in'):
            self.nodeupdate(bpy.context) 
    
    def preexport(self):
        (interval, shour, ehour) = (1, self.cbdm_start_hour - 1, self.cbdm_end_hour - 1) if self.contextmenu == 'CBDM' or (self.contextmenu == 'Compliance' and self.canalysismenu =='3') else (round(self.interval, 3), self.shour, self.ehour)        
        starttime = datetime.datetime(2015, 1, 1, 0) + datetime.timedelta(days = self.sdoy - 1) + datetime.timedelta(hours = shour)

        if self.contextmenu == 'CBDM' or (self.contextmenu == 'Basic' and self.animated):            
            endtime = datetime.datetime(2015, 1, 1, 0) + datetime.timedelta(days = self.edoy - 1)  + datetime.timedelta(hours = ehour)
        elif self.contextmenu == 'Compliance' and self.canalysismenu == '3':
            starttime = datetime.datetime(2015, 1, 1, 0) + datetime.timedelta(hours = shour)
            endtime = datetime.datetime(2015, 1, 1, 0) + datetime.timedelta(days = 364)  + datetime.timedelta(hours = ehour)
        else:
            endtime = starttime

        times = [starttime]
        time = starttime
        while time < endtime:
            time += datetime.timedelta(hours = interval)
            if (self.contextmenu == 'Compliance' and self.canalysismenu == '3') or self.contextmenu == 'CBDM':
                if shour <= time.hour <= ehour:
                    times.append(time)
            else:
                times.append(time)
               
        self.times = times 
        self.starttime = times[0]
        self.endtime = times[-1]
        self['skynum'] = int(self.skymenu)
        self['hours'] = 0 if not self.animated or int(self.skymenu) > 2  else (self.endtime-self.starttime).seconds/3600
        self['epwbase'] = os.path.splitext(os.path.basename(self.inputs['Location in'].links[0].from_node.weather)) if self.inputs['Location in'].links else ''
        self['Text'], self['Options'] = {}, {}
        self['watts'] = 0#1 if self.contextmenu == "CBDM" and self.cbanalysismenu in ('1', '2') else 0
        
    def export(self, scene, export_op):        
        self.startframe = self.startframe if self.animated and self.contextmenu == 'Basic' and self.banalysismenu in ('0', '1', '2') else scene.frame_current 
        self['endframe'] = self.startframe + int(((24 * (self.edoy - self.sdoy) + self.ehour - self.shour)/self.interval)) if self.contextmenu == 'Basic' and self.banalysismenu in ('0', '1', '2') and self.animated else scene.frame_current
        self['mtxfile'] = ''
        self['preview'] = 0
        if self.contextmenu == "Basic":  
            self['preview'] =1
            if self['skynum'] < 4:
                locnode = self.inputs['Location in'].links[0].from_node if self['skynum'] < 3  else 0
                self['skytypeparams'] = ("+s", "+i", "-c", "-b 22.86 -c")[self['skynum']]
                for f, frame in enumerate(range(self.startframe, self['endframe'] + 1)):
                    skytext = sunexport(scene, self, locnode, f) + skyexport(self['skynum'])
                    if self['skynum'] < 2:
                        if frame == self.startframe:
                            if 'SUN' in [ob.data.type for ob in scene.objects if ob.type == 'LAMP' and ob.get('VIType')]:
                                sun = [ob for ob in scene.objects if ob.get('VIType') == 'Sun'][0]
                            else:
                                bpy.ops.object.lamp_add(type='SUN')
                                sun = bpy.context.object
                                sun['VIType'] = 'Sun'
                    if self.hdr:
                        hdrexport(scene, f, frame, self, skytext)
                    self['Text'][str(frame)] = skytext

            elif self['skynum'] == 4:
                if self.hdrname not in bpy.data.images:
                    bpy.data.images.load(self.hdrname)
                self['Text'][str(scene.frame_current)] = hdrsky(self.hdrname, self.hdrmap, self.hdrangle, self.hdrradius)
            
            elif self['skynum'] == 5:
                shutil.copyfile(self.radname, "{}-0.sky".format(scene['viparams']['filebase']))
                with open(self.radname, 'r') as radfiler:
                    self['Text'][str(scene.frame_current)] =  [radfiler.read()]
                    if self.hdr:
                        hdrexport(scene, 0, scene.frame_current, self, radfiler.read())
            elif self['skynum'] == 6:
                self['Text'][str(scene.frame_current)] = ''
        
        elif self.contextmenu == "CBDM":
            if (self.cbanalysismenu =='0' and self.sourcemenu == '0') or (self.cbanalysismenu != '0' and self.sourcemenu2 == '0'):
                self['mtxfile'] = cbdmmtx(self, scene, self.inputs['Location in'].links[0].from_node, export_op)
            elif self.cbanalysismenu != '0' and self.sourcemenu2 == '1':
                self['mtxfile'] = self.mtxname

            if self.cbanalysismenu == '0' :
                self['preview'] = 1
                self['Text'][str(scene.frame_current)] = cbdmhdr(self, scene)
            else:
                self['Text'][str(scene.frame_current)] = "void glow sky_glow \n0 \n0 \n4 1 1 1 0 \nsky_glow source sky \n0 \n0 \n4 0 0 1 180 \nvoid glow ground_glow \n0 \n0 \n4 1 1 1 0 \nground_glow source ground \n0 \n0 \n4 0 0 -1 180\n\n"

                if self.sourcemenu2 == '0':
                    with open("{}.mtx".format(os.path.join(scene['viparams']['newdir'], self['epwbase'][0])), 'r') as mtxfile:
                        self['Options']['MTX'] = mtxfile.read()
                else:
                    with open(self.mtxname, 'r') as mtxfile:
                        self['Options']['MTX'] = mtxfile.read()
                if self.hdr:
                    self['Text'][str(scene.frame_current)] = cbdmhdr(self, scene)

        elif self.contextmenu == "Compliance":
            if self.canalysismenu in ('0', '1', '2'):            
                self['skytypeparams'] = ("-b 22.86 -c", "-b 22.86 -c", "-b 18 -u")[int(self.canalysismenu)]
                skyentry = sunexport(scene, self, 0, 0) + skyexport(3)
                if self.canalysismenu in ('0', '1'):
                    self.starttime = datetime.datetime(2015, 1, 1, 12)
                    self['preview'] = 1
                    if self.hdr:
                        hdrexport(scene, 0, scene.frame_current, self, skyentry)
                else:
                    self.starttime = datetime.datetime(2015, 9, 11, 9)
                self['Text'][str(scene.frame_current)] = skyentry
            else:
                if self.sourcemenu2 == '0':
                    self['mtxfile'] = cbdmmtx(self, scene, self.inputs['Location in'].links[0].from_node, export_op)
                elif self.sourcemenu2 == '1':
                    self['mtxfile'] = self.mtxname
                
                self['Text'][str(scene.frame_current)] = "void glow sky_glow \n0 \n0 \n4 1 1 1 0 \nsky_glow source sky \n0 \n0 \n4 0 0 1 180 \nvoid glow ground_glow \n0 \n0 \n4 1 1 1 0 \nground_glow source ground \n0 \n0 \n4 0 0 -1 180\n\n"

                if self.sourcemenu2 == '0':
                    with open("{}.mtx".format(os.path.join(scene['viparams']['newdir'], self['epwbase'][0])), 'r') as mtxfile:
                        self['Options']['MTX'] = mtxfile.read()
                else:
                    with open(self.mtxname, 'r') as mtxfile:
                        self['Options']['MTX'] = mtxfile.read()
                if self.hdr:
                    self['Text'][str(scene.frame_current)] = cbdmhdr(self, scene)
                
    def postexport(self):  
        typedict = {'Basic': self.banalysismenu, 'Compliance': self.canalysismenu, 'CBDM': self.cbanalysismenu}
        unitdict = {'Basic': ("Lux", '')[int(self.banalysismenu)], 'Compliance': ('DF (%)', 'DF (%)', 'DF (%)', 'sDA (%)')[int(self.canalysismenu)], 'CBDM': ('Mlxh', 'kWh', 'DA (%)')[int(self.cbanalysismenu)]}
        btypedict = {'0': self.bambuildmenu, '1': '', '2': self.bambuildmenu, '3': self.lebuildmenu}
        self['Options'] = {'Context': self.contextmenu, 'Preview': self['preview'], 'Type': typedict[self.contextmenu], 'fs': self.startframe, 'fe': self['endframe'],
                    'anim': self.animated, 'shour': self.shour, 'sdoy': self.sdoy, 'ehour': self.ehour, 'edoy': self.edoy, 'interval': self.interval, 'buildtype': btypedict[self.canalysismenu], 'canalysis': self.canalysismenu, 'storey': self.buildstorey,
                    'bambuild': self.bambuildmenu, 'cbanalysis': self.cbanalysismenu, 'unit': unitdict[self.contextmenu], 'damin': self.damin, 'dalux': self.dalux, 'dasupp': self.dasupp, 'daauto': self.daauto, 'asemax': self.asemax, 'cbdm_sh': self.cbdm_start_hour, 
                    'cbdm_eh': self.cbdm_end_hour, 'weekdays': (7, 5)[self.weekdays], 'sourcemenu': (self.sourcemenu, self.sourcemenu2)[self.cbanalysismenu not in ('2', '3', '4', '5')],
                    'mtxfile': self['mtxfile'], 'times': [t.strftime("%d/%m/%y %H:%M:%S") for t in self.times]}
        nodecolour(self, 0)
        self['exportstate'] = [str(x) for x in (self.contextmenu, self.banalysismenu, self.canalysismenu, self.cbanalysismenu, 
                   self.animated, self.skymenu, self.shour, self.sdoy, self.startmonth, self.endmonth, self.damin, self.dasupp, self.dalux, self.daauto,
                   self.ehour, self.edoy, self.interval, self.hdr, self.hdrname, self.skyname, self.resname, self.turb, self.mtxname, self.cbdm_start_hour,
                   self.cbdm_end_hour, self.bambuildmenu)]

#class ViLiINode(bpy.types.Node, ViNodes):
#    '''Node describing a LiVi rpict simulation'''
#    bl_idname = 'ViLiINode'
#    bl_label = 'LiVi Image'
#    bl_icon = 'LAMP'
#
#    preview = bpy.props.BoolProperty(name = '', default = True)
#
#    def init(self, context):
#        self['nodeid'] = nodeid(self)
#        self.inputs.new('ViLiG', 'Geometry in')
#        self.inputs.new('ViLiC', 'Context in')
#        
#    def draw_buttons(self, context, layout):
#        newrow(layout, 'Preview:', self, 'preview')
#        row = layout.row()
#        row.operator("node.radpreview", text = 'Preview').nodeid = self['nodeid']                           

class ViLiINode(bpy.types.Node, ViNodes):
    '''Node describing a LiVi image generation'''
    bl_idname = 'ViLiINode'
    bl_label = 'LiVi Image'
    bl_icon = 'LAMP'
    
    def nodeupdate(self, context):
        nodecolour(self, self['exportstate'] != [str(x) for x in (self.cusacc, self.simacc, self.pmap, self.x, self.y, self.run, self.illu)])
    
    cusacc = bpy.props.StringProperty(
            name="", description="Custom Radiance simulation parameters", default="", update = nodeupdate)
    simacc = bpy.props.EnumProperty(items=[("0", "Low", "Low accuracy and high speed (preview)"),("1", "Medium", "Medium speed and accuracy"), ("2", "High", "High but slow accuracy"),("3", "Custom", "Edit Radiance parameters"), ],
            name="", description="Simulation accuracy", default="0", update = nodeupdate)
    rpictparams = (("-ab", 2, 3, 4), ("-ad", 256, 1024, 4096), ("-as", 128, 512, 2048), ("-aa", 0, 0, 0), ("-dj", 0, 0.7, 1), ("-ds", 0.5, 0.15, 0.15), ("-dr", 1, 3, 5), ("-ss", 0, 2, 5), ("-st", 1, 0.75, 0.1), ("-lw", 0.0001, 0.00001, 0.0000002), ("-lr", 3, 3, 4))
    pmap = bpy.props.BoolProperty(name = '', default = False, update = nodeupdate)
    pmapgno = bpy.props.IntProperty(name = '', default = 50000)
    pmapcno = bpy.props.IntProperty(name = '', default = 0)
    x = bpy.props.IntProperty(name = '', min = 1, max = 10000, default = 2000, update = nodeupdate)
    y = bpy.props.IntProperty(name = '', min = 1, max = 10000, default = 1000, update = nodeupdate)
    hdrname = bpy.props.StringProperty(name="", description="Name of the composite HDR sky file", default="", update = nodeupdate)
    run = bpy.props.BoolProperty(name = '', default = False, update = nodeupdate) 
    illu = bpy.props.BoolProperty(name = '', default = True, update = nodeupdate)
    
    def init(self, context):
        self['exportstate'] = ''
        self['nodeid'] = nodeid(self)
        self.inputs.new('ViLiG', 'Geometry in')
        self.inputs.new('ViLiC', 'Context in')
        self.outputs.new('ViLiI', 'Image')
        
        
    def draw_buttons(self, context, layout):
        newrow(layout, 'Accuracy:', self, 'simacc')
        if self.simacc == '3':
            newrow(layout, "Radiance parameters:", self, 'cusacc')
        row = layout.row()
        row.operator("node.radpreview", text = 'Preview').nodeid = self['nodeid']  
        newrow(layout, 'X resolution:', self, 'x')
        newrow(layout, 'Y resolution:', self, 'y')
        newrow(layout, 'Illuminance:', self, 'illu')
        newrow(layout, 'Photon map:', self, 'pmap')
        if self.pmap:
           newrow(layout, 'Global photons:', self, 'pmapgno')
           newrow(layout, 'Caustic photons:', self, 'pmapcno')
        row = layout.row()
        row.operator('node.hdrselect', text = 'Select HDR').nodeid = self['nodeid']
        row = layout.row()
        row.prop(self, 'hdrname')
        row = layout.row()
        if not self.run:
            row.operator("node.radimage", text = 'Image').nodeid = self['nodeid']

    def presim(self):
        self['coptions'] = self.inputs['Context in'].links[0].from_node['Options']
        self['goptions'] = self.inputs['Geometry in'].links[0].from_node['Options']
        self['radfiles'], self['reslists'] = {}, [[]]
        self['radparams'] = self.cusacc if self.simacc == '3' else (" {0[0]} {1[0]} {0[1]} {1[1]} {0[2]} {1[2]} {0[3]} {1[3]} {0[4]} {1[4]} {0[5]} {1[5]} {0[6]} {1[6]} {0[7]} {1[7]} {0[8]} {1[8]} {0[9]} {1[9]} {0[10]} {1[10]} ".format([n[0] for n in self.rpictparams], [n[int(self.simacc)+1] for n in self.rpictparams]))
    
    def sim(self, scene):
        self['frames'] = range(scene['liparams']['fs'], scene['liparams']['fe'] + 1)
        
    def postsim(self):
        self.run = 0
        self['exportstate'] = [str(x) for x in (self.cusacc, self.simacc, self.pmap, self.x, self.y, self.run, self.illu)]
        nodecolour(self, 0)   

class ViLiFCNode(bpy.types.Node, ViNodes):
    '''Node describing a LiVi false colour image generation'''
    bl_idname = 'ViLiFCNode'
    bl_label = 'LiVi False Colour Image'
    bl_icon = 'LAMP'  

    def nodeupdate(self, context):
        nodecolour(self, self['exportstate'] != [str(x) for x in (self.hdrname, self.colour, self.lmax, self.unit, self.nscale, self.decades, 
                   self.legend, self.lw, self.lh, self.contour, self.overlay, self.bands)])

    hdrname = bpy.props.StringProperty(name="", description="Name of the composite HDR sky file", default="", update = nodeupdate)    
    colour = bpy.props.EnumProperty(items=[("0", "Default", "Default color mapping"), ("1", "Spectral", "Spectral color mapping"), ("2", "Thermal", "Thermal colour mapping"), ("3", "PM3D", "PM3D colour mapping"), ("4", "Eco", "Eco color mapping")],
            name="", description="Simulation accuracy", default="0", update = nodeupdate)             
    lmax = bpy.props.IntProperty(name = '', min = 0, max = 10000, default = 1000, update = nodeupdate)
    unit = bpy.props.EnumProperty(items=[("0", "Lux", "Spectral color mapping"),("1", "Candelas", "Thermal colour mapping"), ("2", "DF", "PM3D colour mapping"), ("3", "Irradiance(v)", "PM3D colour mapping")],
            name="", description="Unit", default="0", update = nodeupdate)
    nscale = bpy.props.EnumProperty(items=[("0", "Linear", "Linear mapping"),("1", "Log", "Logarithmic mapping")],
            name="", description="Scale", default="0", update = nodeupdate)
    decades = bpy.props.IntProperty(name = '', min = 1, max = 5, default = 2, update = nodeupdate)
    unitdict = {'0': 'Lux', '1': 'cd/m2', '2': 'DF', '3': 'W/m2'}
    unitmult = {'0': 179, '1': 179, '2': 1.79, '3': 1}
    legend  = bpy.props.BoolProperty(name = '', default = True, update = nodeupdate)
    lw = bpy.props.IntProperty(name = '', min = 1, max = 1000, default = 100, update = nodeupdate)
    lh = bpy.props.IntProperty(name = '', min = 1, max = 1000, default = 200, update = nodeupdate)
    contour  = bpy.props.BoolProperty(name = '', default = False, update = nodeupdate)
    overlay  = bpy.props.BoolProperty(name = '', default = False, update = nodeupdate)
    bands  = bpy.props.BoolProperty(name = '', default = False, update = nodeupdate)
    coldict = {'0': 'def', '1': 'spec', '2': 'hot', '3': 'pm3d', '4': 'eco'}

    def init(self, context):
        self['exportstate'] = ''
        self['nodeid'] = nodeid(self)
        self.inputs.new('ViLiI', 'Image')
        
    def draw_buttons(self, context, layout):
        newrow(layout, 'Unit:', self, 'unit')
        newrow(layout, 'Colour:', self, 'colour')
        newrow(layout, 'Legend:', self, 'legend')
        if self.legend:
            newrow(layout, 'Scale:', self, 'nscale')
            if self.nscale == '1':
                newrow(layout, 'Decades:', self, 'decades')
            newrow(layout, 'Legend max:', self, 'lmax')
            newrow(layout, 'Legend width:', self, 'lw')
            newrow(layout, 'Legend height:', self, 'lh')
        newrow(layout, 'Contour:', self, 'contour')
        if self.contour:
           newrow(layout, 'Overlay:', self, 'overlay') 
           newrow(layout, 'Bands:', self, 'bands') 
        row = layout.row()
        row.operator('node.hdrselect', text = 'Select HDR').nodeid = self['nodeid']
        row = layout.row()
        row.prop(self, 'hdrname')
        if self.inputs['Image'].links and self.inputs['Image'].links[0].from_node.hdrname and os.path.isfile(self.inputs['Image'].links[0].from_node.hdrname):
            row = layout.row()
            row.operator("node.livifc", text = 'Process').nodeid = self['nodeid']
            
    def postsim(self):
        self['exportstate'] = [str(x) for x in (self.hdrname, self.colour, self.lmax, self.unit, self.nscale, self.decades, 
                   self.legend, self.lw, self.lh, self.contour, self.overlay, self.bands)]
            
class ViLiSNode(bpy.types.Node, ViNodes):
    '''Node describing a LiVi simulation'''
    bl_idname = 'ViLiSNode'
    bl_label = 'LiVi Simulation'
    bl_icon = 'LAMP'

    def nodeupdate(self, context):
        nodecolour(self, self['exportstate'] != [str(x) for x in (self.cusacc, self.simacc, self.csimacc, self.pmap, self.pmapcno, self.pmapgno)])
        
    simacc = bpy.props.EnumProperty(items=[("0", "Low", "Low accuracy and high speed (preview)"),("1", "Medium", "Medium speed and accuracy"), ("2", "High", "High but slow accuracy"),("3", "Custom", "Edit Radiance parameters"), ],
            name="", description="Simulation accuracy", default="0", update = nodeupdate)
    csimacc = bpy.props.EnumProperty(items=[("0", "Custom", "Edit Radiance parameters"), ("1", "Initial", "Initial accuracy for this metric"), ("2", "Final", "Final accuracy for this metric")],
            name="", description="Simulation accuracy", default="1", update = nodeupdate)
    cusacc = bpy.props.StringProperty(
            name="", description="Custom Radiance simulation parameters", default="", update = nodeupdate)
    rtracebasic = (("-ab", 2, 3, 4), ("-ad", 256, 1024, 4096), ("-as", 128, 512, 2048), ("-aa", 0, 0, 0), ("-dj", 0, 0.7, 1), ("-ds", 0, 0.5, 0.15), ("-dr", 1, 3, 5), ("-ss", 0, 2, 5), ("-st", 1, 0.75, 0.1), ("-lw", 0.0001, 0.00001, 0.000002), ("-lr", 2, 3, 4))
    rtraceadvance = (("-ab", 3, 5), ("-ad", 4096, 8192), ("-as", 512, 1024), ("-aa", 0.0, 0.0), ("-dj", 0.7, 1), ("-ds", 0.5, 0.15), ("-dr", 2, 3), ("-ss", 2, 5), ("-st", 0.75, 0.1), ("-lw", 1e-4, 1e-5), ("-lr", 3, 5))
    rvubasic = (("-ab", 2, 3, 4), ("-ad", 256, 1024, 4096), ("-as", 128, 512, 2048), ("-aa", 0, 0, 0), ("-dj", 0, 0.7, 1), ("-ds", 0.5, 0.15, 0.15), ("-dr", 1, 3, 5), ("-ss", 0, 2, 5), ("-st", 1, 0.75, 0.1), ("-lw", 0.0001, 0.00001, 0.0000002), ("-lr", 3, 3, 4))
    rvuadvance = (("-ab", 3, 5), ("-ad", 4096, 8192), ("-as", 1024, 2048), ("-aa", 0.0, 0.0), ("-dj", 0.7, 1), ("-ds", 0.5, 0.15), ("-dr", 2, 3), ("-ss", 2, 5), ("-st", 0.75, 0.1), ("-lw", 1e-4, 1e-5), ("-lr", 3, 5))
    pmap = bpy.props.BoolProperty(name = '', default = False)
    pmapgno = bpy.props.IntProperty(name = '', default = 50000)
    pmapcno = bpy.props.IntProperty(name = '', default = 0)
    run = bpy.props.IntProperty(default = 0)

    def init(self, context):
        self['nodeid'] = nodeid(self)
        self['simdict'] = {'Basic': 'simacc', 'Compliance':'csimacc', 'CBDM':'csimacc'}
        self.inputs.new('ViLiG', 'Geometry in')
        self.inputs.new('ViLiC', 'Context in')
        self.outputs.new('ViR', 'Results out')
        nodecolour(self, 1)
        self['maxres'], self['minres'], self['avres'], self['exportstate'], self['year'] = {}, {}, {}, '', 2015
        
    def draw_buttons(self, context, layout): 
        scene = context.scene
        try:
            row = layout.row()
            row.label(text = 'Frames: {} - {}'.format(min([c['fs'] for c in (self.inputs['Context in'].links[0].from_node['Options'], self.inputs['Geometry in'].links[0].from_node['Options'])]), max([c['fe'] for c in (self.inputs['Context in'].links[0].from_node['Options'], self.inputs['Geometry in'].links[0].from_node['Options'])])))
            cinnode = self.inputs['Context in'].links[0].from_node
            newrow(layout, 'Photon map:', self, 'pmap')
            if self.pmap:
               newrow(layout, 'Global photons:', self, 'pmapgno')
               newrow(layout, 'Caustic photons:', self, 'pmapcno')
            row = layout.row()
            row.label("Accuracy:")            
            row.prop(self, self['simdict'][cinnode['Options']['Context']])
            
            if (self.simacc == '3' and cinnode['Options']['Context'] == 'Basic') or (self.csimacc == '0' and cinnode['Options']['Context'] in ('Compliance', 'CBDM')):
               newrow(layout, "Radiance parameters:", self, 'cusacc')
            if not self.run:
                if cinnode['Options']['Preview']:
                    row = layout.row()
                    row.operator("node.radpreview", text = 'Preview').nodeid = self['nodeid']
                if cinnode['Options']['Context'] == 'Basic' and cinnode['Options']['Type'] == '1' and not self.run:
                    row.operator("node.liviglare", text = 'Calculate').nodeid = self['nodeid']
                elif [o.name for o in scene.objects if o.name in scene['liparams']['livic']]:
                    row.operator("node.livicalc", text = 'Calculate').nodeid = self['nodeid']
        except Exception as e:
            pass

    def update(self):
        if self.outputs.get('Results out'):
            socklink(self.outputs['Results out'], self['nodeid'].split('@')[1])
        self.run = 0
    
    def presim(self):
        self['coptions'] = self.inputs['Context in'].links[0].from_node['Options']
        self['goptions'] = self.inputs['Geometry in'].links[0].from_node['Options']
        self['radfiles'], self['reslists'] = {}, [[]]
        if self['coptions']['Context'] == 'Basic':
            self['radparams'] = self.cusacc if self.simacc == '3' else (" {0[0]} {1[0]} {0[1]} {1[1]} {0[2]} {1[2]} {0[3]} {1[3]} {0[4]} {1[4]} {0[5]} {1[5]} {0[6]} {1[6]} {0[7]} {1[7]} {0[8]} {1[8]} {0[9]} {1[9]} {0[10]} {1[10]} ".format([n[0] for n in self.rtracebasic], [n[int(self.simacc)+1] for n in self.rtracebasic]))
        else:
            self['radparams'] = self.cusacc if self.csimacc == '0' else (" {0[0]} {1[0]} {0[1]} {1[1]} {0[2]} {1[2]} {0[3]} {1[3]} {0[4]} {1[4]} {0[5]} {1[5]} {0[6]} {1[6]} {0[7]} {1[7]} {0[8]} {1[8]} {0[9]} {1[9]} {0[10]} {1[10]} ".format([n[0] for n in self.rtraceadvance], [n[int(self.csimacc)] for n in self.rtraceadvance]))
    
    def sim(self, scene):
        self['frames'] = range(scene['liparams']['fs'], scene['liparams']['fe'] + 1)
        
    def postsim(self):
        self['exportstate'] = [str(x) for x in (self.cusacc, self.simacc, self.csimacc, self.pmap, self.pmapcno, self.pmapgno)]
        nodecolour(self, 0)

class ViSPNode(bpy.types.Node, ViNodes):
    '''Node describing a VI-Suite sun path'''
    bl_idname = 'ViSPNode'
    bl_label = 'VI Sun Path'
    bl_icon = 'LAMP'

    def init(self, context):
        self['nodeid'] = nodeid(self)
        self.inputs.new('ViLoc', 'Location in')
        nodecolour(self, 1)

    def draw_buttons(self, context, layout):
        if self.inputs['Location in'].links:
            row = layout.row()
            row.operator("node.sunpath", text="Create Sun Path").nodeid = self['nodeid']

    def export(self):
        nodecolour(self, 0)

class ViSSNode(bpy.types.Node, ViNodes):
    '''Node describing a VI-Suite shadow study'''
    bl_idname = 'ViSSNode'
    bl_label = 'VI Shadow Study'
    bl_icon = 'LAMP'

    def nodeupdate(self, context):
        nodecolour(self, self['exportstate'] != [str(x) for x in (self.animmenu, self.sdoy, self.edoy, self.starthour, self.endhour, self.interval, self.cpoint, self.offset)])

    animtype = [('Static', "Static", "Simple static analysis"), ('Geometry', "Geometry", "Animated geometry analysis")]
    animmenu = bpy.props.EnumProperty(name="", description="Animation type", items=animtype, default = 'Static', update = nodeupdate)
    startframe = bpy.props.IntProperty(name = '', default = 0, min = 0, max = 1024, description = 'Start frame')
    endframe = bpy.props.IntProperty(name = '', default = 0, min = 0, max = 1024, description = 'End frame')
    starthour = bpy.props.IntProperty(name = '', default = 1, min = 1, max = 24, description = 'Start hour')
    endhour = bpy.props.IntProperty(name = '', default = 24, min = 1, max = 24, description = 'End hour')
    interval = bpy.props.IntProperty(name = '', default = 1, min = 1, max = 60, description = 'Interval')
    sdoy = bpy.props.IntProperty(name = '', default = 1, min = 1, max = 365, description = 'Start Day', update = nodeupdate)
    edoy = bpy.props.IntProperty(name = '', default = 365, min = 1, max = 365, description = 'End Day', update = nodeupdate)
    cpoint = bpy.props.EnumProperty(items=[("0", "Faces", "Export faces for calculation points"),("1", "Vertices", "Export vertices for calculation points"), ],
            name="", description="Specify the calculation point geometry", default="0", update = nodeupdate)
    offset = bpy.props.FloatProperty(name="", description="Calc point offset", min=0.001, max=1, default=0.01, update = nodeupdate)
    signore = bpy.props.BoolProperty(name = '', default = 0, description = 'Ignore sensor surfaces', update = nodeupdate)
    
    def init(self, context):
        self['nodeid'] = nodeid(self)
        self.inputs.new('ViLoc', 'Location in')
        self.outputs.new('ViR', 'Results out')
        self.outputs['Results out'].hide = True
        self['exportstate'] = ''
        self['goptions'] = {}
        nodecolour(self, 1)

    def draw_buttons(self, context, layout):
        if nodeinputs(self):
            (sdate, edate) = retdates(self.sdoy, self.edoy, self.inputs[0].links[0].from_node['year'])
            newrow(layout, 'Ignore sensor:', self, "signore")
            newrow(layout, 'Animation:', self, "animmenu")
            if self.animmenu != 'Static':            
                row = layout.row(align=True)
                row.alignment = 'EXPAND'
                row.label('Frames:')
                row.prop(self, 'startframe')
                row.prop(self, 'endframe')
            newrow(layout, 'Start day {}/{}:'.format(sdate.day, sdate.month), self, "sdoy")
            newrow(layout, 'End day {}/{}:'.format(edate.day, edate.month), self, "edoy")
            newrow(layout, 'Start hour:', self, "starthour")
            newrow(layout, 'End hour:', self, "endhour")
            newrow(layout, 'Hour steps:', self, "interval")
            newrow(layout, 'Result point:', self, "cpoint")
            newrow(layout, 'Offset:', self, 'offset')
            row = layout.row()
            row.operator("node.shad", text = 'Calculate').nodeid = self['nodeid']

    def preexport(self):
        (self.sdate, self.edate) = retdates(self.sdoy, self.edoy, self.inputs[0].links[0].from_node['year'])
        self['goptions']['offset'] = self.offset

    def postexport(self, scene):
        nodecolour(self, 0)
        self.outputs['Results out'].hide = False if self.get('reslists') else True            
        self['exportstate'] = [str(x) for x in (self.animmenu, self.sdoy, self.edoy, self.starthour, self.endhour, self.interval, self.cpoint, self.offset)]
    
    def update(self):
        if self.outputs.get('Results out'):
            socklink(self.outputs['Results out'], self['nodeid'].split('@')[1])
        
class ViWRNode(bpy.types.Node, ViNodes):
    '''Node describing a VI-Suite wind rose generator'''
    bl_idname = 'ViWRNode'
    bl_label = 'VI Wind Rose'
    bl_icon = 'LAMP'

    def nodeupdate(self, context):
        nodecolour(self, self['exportstate'] != [str(x) for x in (self.wrtype, self.sdoy, self.edoy)])

    wrtype = bpy.props.EnumProperty(items = [("0", "Hist 1", "Stacked histogram"), ("1", "Hist 2", "Stacked Histogram 2"), ("2", "Cont 1", "Filled contour"), ("3", "Cont 2", "Edged contour"), ("4", "Cont 3", "Lined contour")], name = "", default = '0', update = nodeupdate)
    sdoy = bpy.props.IntProperty(name = "", description = "Day of simulation", min = 1, max = 365, default = 1, update = nodeupdate)
    edoy = bpy.props.IntProperty(name = "", description = "Day of simulation", min = 1, max = 365, default = 365, update = nodeupdate)


    def init(self, context):
        self['nodeid'] = nodeid(self)
        self.inputs.new('ViLoc', 'Location in')
        self['exportstate'] = ''
        nodecolour(self, 1)

    def draw_buttons(self, context, layout):
        if nodeinputs(self) and self.inputs[0].links[0].from_node.loc == '1':
            (sdate, edate) = retdates(self.sdoy, self.edoy, self.inputs[0].links[0].from_node['year'])
            newrow(layout, 'Type:', self, "wrtype")
            newrow(layout, 'Start day {}/{}:'.format(sdate.day, sdate.month), self, "sdoy")
            newrow(layout, 'End day {}/{}:'.format(edate.day, edate.month), self, "edoy")
            newrow(layout, 'Colour:', context.scene, 'vi_leg_col')
            row = layout.row()
            row.operator("node.windrose", text="Create Wind Rose").nodeid = self['nodeid']
        else:
            row = layout.row()
            row.label('Location node error')

    def export(self):
        nodecolour(self, 0)
        self['exportstate'] = [str(x) for x in (self.wrtype, self.sdoy, self.edoy)]
        
    def update(self):
        pass

class ViGExEnNode(bpy.types.Node, ViNodes):
    '''Node describing an EnVi Geometry Export'''
    bl_idname = 'ViGExEnNode'
    bl_label = 'EnVi Geometry'

    def init(self, context):
        self['nodeid'] = nodeid(self)
        self.outputs.new('ViEnG', 'Geometry out')
        self['exportstate'] = ''
        nodecolour(self, 1)

    def draw_buttons(self, context, layout):
        row = layout.row()
        row.operator("node.engexport", text = "Export").nodeid = self['nodeid']

    def update(self):
        socklink(self.outputs['Geometry out'], self['nodeid'].split('@')[1])
        
    def preexport(self, scene):
        pass
                
    def postexport(self):
        nodecolour(self, 0)

class ViExEnNode(bpy.types.Node, ViNodes):
    '''Node describing an EnergyPlus export'''
    bl_idname = 'ViExEnNode'
    bl_label = 'EnVi Export'
    bl_icon = 'LAMP'

    def nodeupdate(self, context):
        nodecolour(self, self['exportstate'] != [str(x) for x in (self.loc, self.terrain, self.timesteps, self.animated, self.fs, self.fe, self.sdoy, self.edoy)])

    animated = bpy.props.BoolProperty(name="", description="Animated analysis", update = nodeupdate)
    fs = bpy.props.IntProperty(name="", description="Start frame", default = 0, min = 0, update = nodeupdate)
    fe = bpy.props.IntProperty(name="", description="End frame", default = 0, min = 0, update = nodeupdate)
    loc = bpy.props.StringProperty(name="", description="Identifier for this project", default="", update = nodeupdate)
    terrain = bpy.props.EnumProperty(items=[("0", "City", "Towns, city outskirts, centre of large cities"),
                   ("1", "Urban", "Urban, Industrial, Forest"),("2", "Suburbs", "Rough, Wooded Country, Suburbs"),
                    ("3", "Country", "Flat, Open Country"),("4", "Ocean", "Ocean, very flat country")],
                    name="", description="Specify the surrounding terrain", default="0", update = nodeupdate)

    addonpath = os.path.dirname(inspect.getfile(inspect.currentframe()))
    matpath = addonpath+'/EPFiles/Materials/Materials.data'
    sdoy = bpy.props.IntProperty(name = "", description = "Day of simulation", min = 1, max = 365, default = 1, update = nodeupdate)
    edoy = bpy.props.IntProperty(name = "", description = "Day of simulation", min = 1, max = 365, default = 365, update = nodeupdate)
    timesteps = bpy.props.IntProperty(name = "", description = "Time steps per hour", min = 1, max = 60, default = 1, update = nodeupdate)
    restype= bpy.props.EnumProperty(items = [("0", "Zone Thermal", "Thermal Results"), ("1", "Comfort", "Comfort Results"), ("2", "Zone Ventilation", "Zone Ventilation Results"), 
                                             ("3", "Ventilation Link", "Ventilation Link Results"), ("4", "Thermal Chimney", "Thermal Chimney Results")],
                                   name="", description="Specify the EnVi results category", default="0", update = nodeupdate)

    (resaam, resaws, resawd, resah, resasm, restt, resh, restwh, restwc, reswsg, rescpp, rescpm, resvls, resvmh, resim, resiach, resco2, resihl, resl12ms,
     reslof, resmrt, resocc, resh, resfhb, ressah, ressac, reshrhw, restcvf, restcmf, restcot, restchl, restchg, restcv, restcm, resldp) = resnameunits()
     
    def init(self, context):
        self['nodeid'] = nodeid(self)
        self.outputs.new('ViEnC', 'Context out')
        self.inputs.new('ViEnG', 'Geometry in')
        self.inputs.new('ViLoc', 'Location in')
        self['exportstate'] = ''
        self['year'] = 2015
        nodecolour(self, 1)

    def draw_buttons(self, context, layout):
        (sdate, edate) = retdates(self.sdoy, self.edoy, self['year'])
        row = layout.row()
        row.label('Animation:')
        row.prop(self, 'animated')
        if self.animated:
            newrow(layout, 'Start frame:', self, 'fs')
            newrow(layout, 'End frame:', self, 'fe')
        newrow(layout, "Name/location", self, "loc")
        row = layout.row()
        row.label(text = 'Terrain:')
        col = row.column()
        col.prop(self, "terrain")
        newrow(layout, 'Start day {}/{}:'.format(sdate.day, sdate.month), self, "sdoy")
        newrow(layout, 'End day {}/{}:'.format(edate.day, edate.month), self, "edoy")
        newrow(layout, 'Time-steps/hour', self, "timesteps")
        row = layout.row()
        row.label(text = 'Results Category:')
        col = row.column()
        col.prop(self, "restype")
        resdict = enresprops('')
        for rprop in resdict[self.restype]:
            if not rprop:
                row = layout.row()
            else:
                row.prop(self, rprop)
        if all([s.links for s in self.inputs]) and not any([s.links[0].from_node.use_custom_color for s in self.inputs]):
            row = layout.row()
            row.operator("node.enexport", text = 'Export').nodeid = self['nodeid']

    def update(self):
        if self.inputs.get('Location in') and self.outputs.get('Context out'):
            socklink(self.outputs['Context out'], self['nodeid'].split('@')[1])
            self['year'] = self.inputs['Location in'].links[0].from_node['year'] if self.inputs['Location in'].links else 2015
    
    def preexport(self, scene):
        (self.fs, self.fe) = (self.fs, self.fe) if self.animated else (scene.frame_current, scene.frame_current)
        scene['enparams']['fs'], scene['enparams']['fe'] = self.fs, self.fe
        (self.sdate, self.edate) = retdates(self.sdoy, self.edoy, self['year'])
        
    def postexport(self):
        nodecolour(self, 0)
        self['exportstate'] = [str(x) for x in (self.loc, self.terrain, self.timesteps, self.animated, self.fs, self.fe, self.sdoy, self.edoy)]

class ViEnSimNode(bpy.types.Node, ViNodes):
    '''Node describing an EnergyPlus simulation'''
    bl_idname = 'ViEnSimNode'
    bl_label = 'EnVi Simulation'
    bl_icon = 'LAMP'

    def init(self, context):
        self['nodeid'] = nodeid(self)
        self.inputs.new('ViEnC', 'Context in')
        self.outputs.new('ViR', 'Results out')
        self['exportstate'] = ''
        self['Start'], self['End'] = 1, 365
        self['AStart'], self['AEnd'] = 0, 0
        nodecolour(self, 1)

    def nodeupdate(self, context):
        nodecolour(self, self['exportstate'] != [self.resname])

    resname = bpy.props.StringProperty(name="", description="Base name for the results files", default="results", update = nodeupdate)
    resfilename = bpy.props.StringProperty(name = "", default = 'results')
    dsdoy, dedoy, run  = bpy.props.IntProperty(), bpy.props.IntProperty(), bpy.props.IntProperty(min = -1, default = -1)

    def draw_buttons(self, context, layout):
        if self.run > -1:
            row = layout.row()
            row.label('Calculating {}%'.format(self.run))
        elif self.inputs['Context in'].links and not self.inputs['Context in'].links[0].from_node.use_custom_color:
            newrow(layout, 'Results name:', self, 'resname')
            row = layout.row()
            row.operator("node.ensim", text = 'Calculate').nodeid = self['nodeid']

    def update(self):
        if self.outputs.get('Results out'):
            socklink(self.outputs['Results out'], self['nodeid'].split('@')[1])

    def presim(self, context):
        innode = self.inputs['Context in'].links[0].from_node
        self['frames'] = range(context.scene['enparams']['fs'], context.scene['enparams']['fe'] + 1)
        self['year'] = innode['year']
        self.dsdoy = innode.sdoy # (locnode.startmonthnode.sdoy
        self.dedoy = innode.edoy
        self["_RNA_UI"] = {"Start": {"min":innode.sdoy, "max":innode.edoy}, "End": {"min":innode.sdoy, "max":innode.edoy}, "AStart": {"name": '', "min":context.scene['enparams']['fs'], "max":context.scene['enparams']['fe']}, "AEnd": {"min":context.scene['enparams']['fs'], "max":context.scene['enparams']['fe']}}
        self['Start'], self['End'] = innode.sdoy, innode.edoy
#        self["_RNA_UI"] = {"AStart": {"min":context.scene['enparams']['fs'], "max":context.scene['enparams']['fe']}, "AEnd": {"min":context.scene['enparams']['fs'], "max":context.scene['enparams']['fe']}}
        self['AStart'], self['AEnd'] = context.scene['enparams']['fs'], context.scene['enparams']['fe']
        
class ViEnRFNode(bpy.types.Node, ViNodes):
    '''Node for EnergyPlus results file selection'''
    bl_idname = 'ViEnRFNode'
    bl_label = 'EnVi Results File'

    def nodeupdate(self, context):
        nodecolour(self, self['exportstate'] != [self.resfilename])
        self['frames'] = [context.scene.frame_current]
        
    resfilename = bpy.props.StringProperty(name="", description="Name of the EnVi results file", default="", update=nodeupdate)
    filebase = bpy.props.StringProperty(name="", description="Name of the EnVi results file", default="")
    dsdoy, dedoy = bpy.props.IntProperty(), bpy.props.IntProperty()
    

    def init(self, context):
        self['nodeid'] = nodeid(self)
        self.outputs.new('ViR', 'Results out')
        self['exportstate'] = ''
        self['year'] = 2015        
        nodecolour(self, 1)

    def draw_buttons(self, context, layout):
        row = layout.row()
        row.label('ESO file:')
        row.operator('node.esoselect', text = 'Select file').nodeid = self['nodeid']
        row = layout.row()
        row.prop(self, 'resfilename')
        row.operator("node.fileprocess", text = 'Process file').nodeid = self['nodeid']

    def update(self):
        socklink(self.outputs['Results out'], self['nodeid'].split('@')[1])

    def export(self):
        self['exportstate'] = [self.resfilename]
        nodecolour(self, 0)

class ViEnInNode(bpy.types.Node, ViNodes):
    '''Node for EnergyPlus input file selection'''
    bl_idname = 'ViEnInNode'
    bl_label = 'EnVi Input File'
    
    def nodeupdate(self, context):
        context.scene['enparams']['fs'] = context.scene['enparams']['fe'] = context.scene.frame_current            
        shutil.copyfile(self.idffilename, os.path.join(context.scene['viparams']['newdir'], 'in{}.idf'.format(context.scene.frame_current)))
        locnode = self.inputs['Location in'].links[0].from_node
        self['year'] = locnode['year']
        shutil.copyfile(locnode.weather, os.path.join(context.scene['viparams']['newdir'], 'in{}.epw'.format(context.scene.frame_current)))

        with open(self.idffilename, 'r', errors='ignore') as idff:
            idfflines = idff.readlines()
            for l, line in enumerate(idfflines):
                if line.split(',')[0].lstrip(' ').upper() == 'RUNPERIOD':
                    self.sdoy = datetime.datetime(self['year'], int(idfflines[l+2].split(',')[0].lstrip(' ')), int(idfflines[l+3].split(',')[0].lstrip(' '))).timetuple().tm_yday
                    self.edoy = datetime.datetime(self['year'], int(idfflines[l+4].split(',')[0].lstrip(' ')), int(idfflines[l+5].split(',')[0].lstrip(' '))).timetuple().tm_yday
                    self.outputs['Context out'].hide = False
                    break
            nodecolour(self, 0)

    idffilename = bpy.props.StringProperty(name="", description="Name of the EnVi results file", default="", update=nodeupdate)
    sdoy = bpy.props.IntProperty(name = '', default = 1, min = 1, max = 365)
    edoy = bpy.props.IntProperty(name = '', default = 365, min = 1, max = 365)
    newdir = bpy.props.StringProperty()

    def init(self, context):
        self.inputs.new('ViLoc', 'Location in')
        self.outputs.new('ViEnC', 'Context out')
        self.outputs['Context out'].hide = True
        self['nodeid'] = nodeid(self)
        nodecolour(self, 1)

    def draw_buttons(self, context, layout):
        row = layout.row()
        if self.inputs['Location in'].links:            
            row.label('ESO file:')
            row.operator('node.idfselect', text = 'Select IDF file').nodeid = self['nodeid']
            row = layout.row()
            row.prop(self, 'idffilename')
        else:
            row.label('Connect Location node')

    def update(self):
        socklink(self.outputs['Context out'], self['nodeid'].split('@')[1])
        if not self.inputs['Location in'].links:
            nodecolour(self, 1)

class ViResSock(bpy.types.NodeSocket):
    '''Results socket'''
    bl_idname = 'ViEnRIn'
    bl_label = 'Results axis'
    valid = ['Vi Results']

    def draw(self, context, layout, node, text):
        typedict = {"Time": [], "Frames": [], "Climate": ['climmenu'], "Zone": ("zonemenu", "zonermenu"), "Linkage":("linkmenu", "linkrmenu"), "External node":("enmenu", "enrmenu"), "Chimney":("chimmenu", "chimrmenu"), "Position":("posmenu", "posrmenu"), "Camera":("cammenu", "camrmenu")}
        row = layout.row()

        if self.links and self.links[0].from_node.get('frames'):
            if len(self.links[0].from_node['frames']) > 1 and node.parametricmenu == '0': 
                row.prop(self, "framemenu", text = text)
                row.prop(self, "rtypemenu")
            else:
                row.prop(self, "rtypemenu", text = text)

            for rtype in typedict[self.rtypemenu]:
                row.prop(self, rtype)
            if self.node.timemenu in ('1', '2') and self.rtypemenu !='Time' and node.parametricmenu == '0':
                row.prop(self, "statmenu")
            if self.rtypemenu != 'Time':
                row.prop(self, 'multfactor')
        else:
            row.label('No results')

    def draw_color(self, context, node):
        return (0.0, 1.0, 0.0, 0.75)
        
class ViResUSock(bpy.types.NodeSocket):
    '''Vi unlinked results socket'''
    bl_idname = 'ViEnRInU'
    bl_label = 'Axis'
    valid = ['Vi Results']

    def draw_color(self, context, node):
        return (0.0, 1.0, 0.0, 0.75)

    def draw(self, context, layout, node, text):
        layout.label(self.bl_label)
    
class ViEnRNode(bpy.types.Node, ViNodes):
    '''Node for 2D results plotting'''
    bl_idname = 'ViChNode'
    bl_label = 'VI Chart'
    
    def aupdate(self, context):
        self.update()

    def pmitems(self, context):
        return [tuple(p) for p in self['pmitems']]

    ctypes = [("0", "Line/Scatter", "Line/Scatter Plot")]
    charttype = bpy.props.EnumProperty(items = ctypes, name = "Chart Type", default = "0")
    timemenu = bpy.props.EnumProperty(items=[("0", "Hourly", "Hourly results"),("1", "Daily", "Daily results"), ("2", "Monthly", "Monthly results")],
                name="", description="Results frequency", default="0")
    parametricmenu = bpy.props.EnumProperty(items=pmitems, name="", description="Parametric result display", update=aupdate)    
    bl_width_max = 800
           
    def init(self, context):
        self['nodeid'] = nodeid(self)
        self.inputs.new("ViEnRXIn", "X-axis")
        self.inputs.new("ViEnRY1In", "Y-axis 1")
        self.inputs["Y-axis 1"].hide = True
        self.inputs.new("ViEnRY2In", "Y-axis 2")
        self.inputs["Y-axis 2"].hide = True
        self.inputs.new("ViEnRY3In", "Y-axis 3")
        self.inputs["Y-axis 3"].hide = True
        self['Start'], self['End'] = 1, 365
        self['pmitems'] = [("0", "Static", "Static results")]
        self.update()

    def draw_buttons(self, context, layout):
        if self.inputs['X-axis'].links:
            innode = self.inputs['X-axis'].links[0].from_node
            if innode.get('reslists'):
                newrow(layout, 'Animated:', self, 'parametricmenu')
                if self.parametricmenu == '0':                
                    (sdate, edate) = retdates(self['Start'], self['End'], innode['year']) 
                    label = "Start/End Day: {}/{} {}/{}".format(sdate.day, sdate.month, edate.day, edate.month)
                else:
                    row = layout.row()
                    label = "Frame"
     
                row = layout.row()    
                row.label(label)
                row.prop(self, '["Start"]')
                row.prop(self, '["End"]')
                    
                if self.parametricmenu == '0':
                    row = layout.row()
                    row.prop(self, "charttype")
                    row.prop(self, "timemenu")
    
                if self.inputs['Y-axis 1'].links and 'NodeSocketUndefined' not in [sock.bl_idname for sock in self.inputs if sock.links]:
                    layout.operator("node.chart", text = 'Create plot').nodeid = self['nodeid']
                    row = layout.row()
                    row.label("------------------")

    def update(self):
        try:
            if not self.inputs['X-axis'].links or not self.inputs['X-axis'].links[0].from_node['reslists']:
                class ViEnRXIn(ViResUSock):
                    '''Energy geometry out socket'''
                    bl_idname = 'ViEnRXIn'
                    bl_label = 'X-axis'    
                    valid = ['Vi Results']
                    
            else:
                innode = self.inputs['X-axis'].links[0].from_node
                rl = innode['reslists']
                zrl = list(zip(*rl))
                try:
                    if len(set(zrl[0])) > 1:
                        self['pmitems'] = [("0", "Static", "Static results"), ("1", "Parametric", "Parametric results")]
                    else:
                        self['pmitems'] = [("0", "Static", "Static results")]
                except:
                    self['pmitems'] = [("0", "Static", "Static results")]
                
                time.sleep(0.1)
    
                if self.parametricmenu == '1' and len(set(zrl[0])) > 1:
                    frames = [int(k) for k in set(zrl[0]) if k != 'All']
                    startframe, endframe = min(frames), max(frames)
                    self["_RNA_UI"] = {"Start": {"min":startframe, "max":endframe}, "End": {"min":startframe, "max":endframe}}
                    self['Start'], self['End'] = startframe, endframe
                else:
                    if 'Month' in zrl[3]:
                        startday = datetime.datetime(int(innode['year']), int(zrl[4][zrl[3].index('Month')].split()[0]), int(zrl[4][zrl[3].index('Day')].split()[0])).timetuple().tm_yday
                        endday = datetime.datetime(int(innode['year']), int(zrl[4][zrl[3].index('Month')].split()[-1]), int(zrl[4][zrl[3].index('Day')].split()[-1])).timetuple().tm_yday
                        self["_RNA_UI"] = {"Start": {"min":startday, "max":endday}, "End": {"min":startday, "max":endday}}
                        self['Start'], self['End'] = startday, endday
    
                if self.inputs.get('Y-axis 1'):
                    self.inputs['Y-axis 1'].hide = False
    
                class ViEnRXIn(ViResSock):
                    '''Energy geometry out socket'''
                    bl_idname = 'ViEnRXIn'
                    bl_label = 'X-axis'
                                    
#                    if innode['reslists']:
                    (valid, framemenu, statmenu, rtypemenu, climmenu, zonemenu, zonermenu, linkmenu, linkrmenu, enmenu, enrmenu, chimmenu, chimrmenu, posmenu, posrmenu, cammenu, camrmenu, multfactor) = retrmenus(innode, self)
                        
            bpy.utils.register_class(ViEnRXIn)
    
            if self.inputs.get('Y-axis 1'):
                if not self.inputs['Y-axis 1'].links or not self.inputs['Y-axis 1'].links[0].from_node['reslists']:
                    class ViEnRY1In(ViResUSock):
                        '''Energy geometry out socket'''
                        bl_idname = 'ViEnRY1In'
                        bl_label = 'Y-axis 1'
    
                    if self.inputs.get('Y-axis 2'):
                        self.inputs['Y-axis 2'].hide = True
                else:
                    innode = self.inputs['Y-axis 1'].links[0].from_node
    
                    class ViEnRY1In(ViResSock):
                        '''Energy geometry out socket'''
                        bl_idname = 'ViEnRY1In'
                        bl_label = 'Y-axis 1'
                        (valid, framemenu, statmenu, rtypemenu, climmenu, zonemenu, zonermenu, linkmenu, linkrmenu, enmenu, enrmenu, chimmenu, chimrmenu, posmenu, posrmenu, cammenu, camrmenu, multfactor) = retrmenus(innode, self)
    
                    self.inputs['Y-axis 2'].hide = False
                bpy.utils.register_class(ViEnRY1In)
    
            if self.inputs.get('Y-axis 2'):
                if not self.inputs['Y-axis 2'].links or not self.inputs['Y-axis 2'].links[0].from_node['reslists']:
                    class ViEnRY2In(ViResUSock):
                        '''Energy geometry out socket'''
                        bl_idname = 'ViEnRY2In'
                        bl_label = 'Y-axis 2'
    
                    if self.inputs.get('Y-axis 3'):
                        self.inputs['Y-axis 3'].hide = True
                else:
                    innode = self.inputs[2].links[0].from_node
    
                    class ViEnRY2In(ViResSock):
                        '''Energy geometry out socket'''
                        bl_idname = 'ViEnRY2In'
                        bl_label = 'Y-axis 2'
    
                        (valid, framemenu, statmenu, rtypemenu, climmenu, zonemenu, zonermenu, linkmenu, linkrmenu, enmenu, enrmenu, chimmenu, chimrmenu, posmenu, posrmenu, cammenu, camrmenu, multfactor) = retrmenus(innode, self)
    
                    self.inputs['Y-axis 3'].hide = False
    
                bpy.utils.register_class(ViEnRY2In)
    
            if self.inputs.get('Y-axis 3'):
                if not self.inputs['Y-axis 3'].links or not self.inputs['Y-axis 3'].links[0].from_node['reslists']:
                    class ViEnRY3In(ViResUSock):
                        '''Energy geometry out socket'''
                        bl_idname = 'ViEnRY3In'
                        bl_label = 'Y-axis 3'
                else:
                    innode = self.inputs[3].links[0].from_node
    
                    class ViEnRY3In(ViResSock):
                        '''Energy geometry out socket'''
                        bl_idname = 'ViEnRY3In'
                        bl_label = 'Y-axis 3'
    
                        (valid, framemenu, statmenu, rtypemenu, climmenu, zonemenu, zonermenu, linkmenu, linkrmenu, enmenu, enrmenu, chimmenu, chimrmenu, posmenu, posrmenu, cammenu, camrmenu, multfactor) = retrmenus(innode, self)
    
                bpy.utils.register_class(ViEnRY3In)
        except Exception as e:
            print('Chart node update failure 2 ', e)

class ViNodeCategory(NodeCategory):
    @classmethod
    def poll(cls, context):
        return context.space_data.tree_type == 'ViN'

class ViLocSock(bpy.types.NodeSocket):
    '''Vi Location socket'''
    bl_idname = 'ViLoc'
    bl_label = 'Location socket'
    valid = ['Location']

    def draw(self, context, layout, node, text):
        layout.label(text)

    def draw_color(self, context, node):
        return (0.45, 1.0, 0.45, 1.0)

class ViLiWResOut(bpy.types.NodeSocket):
    '''LiVi irradiance out socket'''
    bl_idname = 'LiViWOut'
    bl_label = 'LiVi W/m2 out'

    valid = ['LiViWatts']
    link_limit = 1

    def draw(self, context, layout, node, text):
        layout.label(text)

    def draw_color(self, context, node):
        return (1.0, 0.2, 0.2, 0.75)
        
class ViLiCBDMSock(bpy.types.NodeSocket):
    '''LiVi irradiance out socket'''
    bl_idname = 'ViLiCBDM'
    bl_label = 'LiVi CBDM context socket'

    valid = ['CBDM']
#    link_limit = 1

    def draw(self, context, layout, node, text):
        layout.label(text)

    def draw_color(self, context, node):
        return (1.0, 1.0, 1.0, 0.75)
    

class ViLiGSock(bpy.types.NodeSocket):
    '''Lighting geometry socket'''
    bl_idname = 'ViLiG'
    bl_label = 'Geometry'

    valid = ['LiVi Geometry', 'text']
    link_limit = 1

    def draw(self, context, layout, node, text):
        layout.label(text)

    def draw_color(self, context, node):
        return (0.3, 0.17, 0.07, 0.75)

class ViLiCSock(bpy.types.NodeSocket):
    '''Lighting context in socket'''
    bl_idname = 'ViLiC'
    bl_label = 'Context'

    valid = ['LiVi Context', 'text']
    link_limit = 1

    def draw(self, context, layout, node, text):
        layout.label(text)

    def draw_color(self, context, node):
        return (1.0, 1.0, 0.0, 0.75)
    
class ViLiISock(bpy.types.NodeSocket):
    '''Lighting context in socket'''
    bl_idname = 'ViLiI'
    bl_label = 'Image'

    valid = ['image']
    link_limit = 1

    def draw(self, context, layout, node, text):
        layout.label(text)

    def draw_color(self, context, node):
        return (0.5, 1.0, 0.0, 0.75)
        
class ViGen(bpy.types.NodeSocket):
    '''VI Generative geometry socket'''
    bl_idname = 'ViGen'
    bl_label = 'Generative geometry'

    valid = ['LiVi GeoGen']
    link_limit = 1

    def draw(self, context, layout, node, text):
        layout.label(text)

    def draw_color(self, context, node):
        return (0.0, 1.0, 1.0, 0.75)

class ViTar(bpy.types.NodeSocket):
    '''VI Generative target socket'''
    bl_idname = 'ViTar'
    bl_label = 'Generative target'

    valid = ['LiVi TarGen']
    link_limit = 1

    def draw(self, context, layout, node, text):
        layout.label(text)

    def draw_color(self, context, node):
        return (1.0, 0.0, 1.0, 0.75)

class ViEnG(bpy.types.NodeSocket):
    '''Energy geometry out socket'''
    bl_idname = 'ViEnG'
    bl_label = 'EnVi Geometry'

    valid = ['EnVi Geometry']
    link_limit = 1

    def draw(self, context, layout, node, text):
        layout.label(text)

    def draw_color(self, context, node):
        return (0.0, 0.0, 1.0, 0.75)

class ViR(bpy.types.NodeSocket):
    '''Vi results socket'''
    bl_idname = 'ViR'
    bl_label = 'Vi results'

    valid = ['Vi Results']
    link_limit = 1

    def draw(self, context, layout, node, text):
        layout.label(text)

    def draw_color(self, context, node):
        return (0.0, 1.0, 0.0, 0.75)

class ViText(bpy.types.NodeSocket):
    '''VI text socket'''
    bl_idname = 'ViText'
    bl_label = 'VI text export'

    valid = ['text']
    link_limit = 1

    def draw(self, context, layout, node, text):
        layout.label(text)

    def draw_color(self, context, node):
        return (0.2, 1.0, 0.0, 0.75)

class ViEnC(bpy.types.NodeSocket):
    '''EnVi context socket'''
    bl_idname = 'ViEnC'
    bl_label = 'EnVi context'

    valid = ['EnVi Context']
    link_limit = 1

    def draw(self, context, layout, node, text):
        layout.label(text)

    def draw_color(self, context, node):
        return (0.0, 1.0, 1.0, 0.75)

class EnViDataIn(bpy.types.NodeSocket):
    '''EnVi data in socket'''
    bl_idname = 'EnViDIn'
    bl_label = 'EnVi data in socket'

    valid = ['EnVi data']
    link_limit = 1

    def draw(self, context, layout, node, text):
        layout.label(text)

    def draw_color(self, context, node):
        return (0.0, 1.0, 0.0, 0.75)

# Generative nodes
class ViGenNode(bpy.types.Node, ViNodes):
    '''Generative geometry manipulation node'''
    bl_idname = 'ViGenNode'
    bl_label = 'VI Generative'
    bl_icon = 'LAMP'

    geotype = [('Object', "Object", "Object level manipulation"), ('Mesh', "Mesh", "Mesh level manipulation")]
    geomenu = bpy.props.EnumProperty(name="", description="Geometry type", items=geotype, default = 'Mesh')
    seltype = [('All', "All", "All geometry"), ('Selected', "Selected", "Only selected geometry"), ('Not selected', "Not selected", "Only unselected geometry")]
    oselmenu = bpy.props.EnumProperty(name="", description="Object selection", items=seltype, default = 'Selected')
    mselmenu = bpy.props.EnumProperty(name="", description="Mesh selection", items=seltype, default = 'Selected')
    omantype = [('0', "Move", "Move geometry"), ('1', "Rotate", "Only unselected geometry"), ('2', "Scale", "Scale geometry")]
    omanmenu = bpy.props.EnumProperty(name="", description="Manipulation type", items=omantype, default = '0')
    mmantype = [('0', "Move", "Move geometry"), ('1', "Rotate", "Only unselected geometry"), ('2', "Scale", "Scale geometry"), ('3', "Extrude", "Extrude geometry")]
    mmanmenu = bpy.props.EnumProperty(name="", description="Manipulation type", items=mmantype, default = '0')
    (x, y, z) = [bpy.props.FloatProperty(name = i, min = -1, max = 1, default = 1) for i in ('X', 'Y', 'Z')]
    normal = bpy.props.BoolProperty(name = '', default = False)
    extent = bpy.props.FloatProperty(name = '', min = -360, max = 360, default = 0)
    steps = bpy.props.IntProperty(name = '', min = 1, max = 100, default = 1)

    def init(self, context):
        self['nodeid'] = nodeid(self)
        self.outputs.new('ViGen', 'Generative out')

    def draw_buttons(self, context, layout):
        newrow(layout, 'Geometry:', self, 'geomenu')
        newrow(layout, 'Object Selection:', self, 'oselmenu')
        if self.geomenu == 'Object':
           newrow(layout, 'Manipulation:', self, 'omanmenu')
           row = layout.row()
           col = row.column()
           subrow = col.row(align=True)
           subrow.prop(self, 'x')
           subrow.prop(self, 'y')
           subrow.prop(self, 'z')
        else:
           newrow(layout, 'Mesh Selection:', self, 'mselmenu')
           newrow(layout, 'Manipulation:', self, 'mmanmenu')
           newrow(layout, 'Normal:', self, 'normal')
           if not self.normal:
               row = layout.row()
               col = row.column()
               subrow = col.row(align=True)
               subrow.prop(self, 'x')
               subrow.prop(self, 'y')
               subrow.prop(self, 'z')

        newrow(layout, 'Extent:', self, 'extent')
        newrow(layout, 'Increment:', self, 'steps')

    def update(self):
        socklink(self.outputs['Generative out'], self['nodeid'].split('@')[1])
        if self.outputs['Generative out'].links:
            nodecolour(self, self.outputs['Generative out'].links[0].to_node.animmenu != 'Static')

class ViTarNode(bpy.types.Node, ViNodes):
    '''Target Node'''
    bl_idname = 'ViTarNode'
    bl_label = 'VI Target'
    bl_icon = 'LAMP'

    ab = bpy.props.EnumProperty(items=[("0", "Above", "Target is above level"),("1", "Below", "Target is below level")],  name="", description="Whether target is to go above or below a specified level", default="0")
    stat = bpy.props.EnumProperty(items=[("0", "Average", "Average of data points"),("1", "Max", "Maximum of data points"),("2", "Min", "Minimum of data points"),("3", "Tot", "Total of data points")],  name="", description="Metric statistic", default="0")
    value = bpy.props.FloatProperty(name = '', min = 0, max = 100000, default = 0, description="Desired value")

    def init(self, context):
        self['nodeid'] = nodeid(self)
        self.outputs.new('ViTar', 'Target out')

    def draw_buttons(self, context, layout):
        newrow(layout, 'Statistic:', self, 'stat')
        newrow(layout, 'Above/Below:', self, 'ab')
        newrow(layout, 'Value:', self, 'value')

class ViCSVExport(bpy.types.Node, ViNodes):
    '''CSV Export Node'''
    bl_idname = 'ViCSV'
    bl_label = 'VI CSV Export'
    bl_icon = 'LAMP'
    
    animated = bpy.props.BoolProperty(name = '', description = 'Animated results', default = 0)

    def init(self, context):
        self['nodeid'] = nodeid(self)
        self.inputs.new('ViR', 'Results in')

    def draw_buttons(self, context, layout):
        try:
            rl = self.inputs['Results in'].links[0].from_node['reslists']
            zrl = list(zip(*rl))
            if len(set(zrl[0])) > 1:
                newrow(layout, 'Animated:', self, 'animated')
            row = layout.row()
            row.operator('node.csvexport', text = 'Export CSV file').nodeid = self['nodeid']
        except:
            pass
        
    def update(self):
        pass

class ViTextEdit(bpy.types.Node, ViNodes):
    '''Text Export Node'''
    bl_idname = 'ViTextEdit'
    bl_label = 'VI Text Edit'
    bl_icon = 'LAMP'
    
    contextmenu = bpy.props.StringProperty(name = '')

    def init(self, context):
        self['nodeid'] = nodeid(self)
        self['bt'] = ''
        self.outputs.new('ViText', 'Text out')
        self.inputs.new('ViText', 'Text in')
        self.outputs['Text out']['Text'] = {}
        self.outputs['Text out']['Options'] = {}
        
    def draw_buttons(self, context, layout):
        if self.inputs['Text in'].links:
            inodename = self.inputs['Text in'].links[0].from_node.name
            row = layout.row()
            row.label(text = 'Text name: {}'.format(inodename))            
            if inodename in [im.name for im in bpy.data.texts] and self['bt'] != bpy.data.texts[inodename].as_string():
                row = layout.row()
                row.operator('node.textupdate', text = 'Update').nodeid = self['nodeid']

    def update(self):
        socklink(self.outputs['Text out'], self['nodeid'].split('@')[1])
        if self.inputs and self.inputs['Text in'].links:
            self['Options'] = self.inputs['Text in'].links[0].from_node['Options']
            self['Text'] = self.inputs['Text in'].links[0].from_node['Text']
            inodename = self.inputs['Text in'].links[0].from_node.name
            sframes = sorted([int(frame) for frame in self.inputs['Text in'].links[0].from_node['Text'].keys()])
            t = ''.join(['# Frame {}\n{}\n\n'.format(f, self.inputs['Text in'].links[0].from_node['Text'][str(f)]) for f in sframes])
            bt = bpy.data.texts.new(inodename) if inodename not in [im.name for im in bpy.data.texts] else bpy.data.texts[inodename]
            bt.from_string(t)
            self['bt'] = bt.as_string()
        else:
            self['Text'] = {}

    def textupdate(self, bt):
        inodename = self.inputs['Text in'].links[0].from_node.name
        bt = bpy.data.texts.new(inodename) if inodename not in [im.name for im in bpy.data.texts] else bpy.data.texts[inodename]
        btlines = [line.body for line in bt.lines]
        self['bt'] = bt.as_string()
        btheads = [line for line in btlines if '# Frame' in line]
        btstring = ''.join([self['bt'].replace(bth, '***') for bth in btheads])
        btbodies = btstring.split('***\n')[1:]
        btframes = [head.split()[2] for head in btheads]
        self['Text'] = {bthb[0]:bthb[1] for bthb in zip(btframes, btbodies)}

class ViTextExport(bpy.types.Node, ViNodes):
    '''Text Export Node'''
    bl_idname = 'ViText'
    bl_label = 'VI Text Export'
    bl_icon = 'LAMP'

    etoggle = bpy.props.BoolProperty(name = '', default = False)

    def init(self, context):
        self['nodeid'] = nodeid(self)
        self.inputs.new('ViText', 'Text in')

    def draw_buttons(self, context, layout):
        if self.inputs['Text in'].links:
            newrow(layout, 'Edit:', self, 'etoggle')
            row = layout.row()
            row.operator('node.textexport', text = 'Export text file').nodeid = self['nodeid']

    def update(self):
        pass

# Openfoam nodes

class VIOfM(bpy.types.NodeSocket):
    '''FloVi mesh socket'''
    bl_idname = 'VIOfM'
    bl_label = 'FloVi Mesh socket'

    valid = ['FloVi mesh']
    link_limit = 1

    def draw(self, context, layout, node, text):
        layout.label(text)

    def draw_color(self, context, node):
        return (0.5, 1.0, 0.0, 0.75)

class VIOFCDS(bpy.types.NodeSocket):
    '''FloVi ControlDict socket'''
    bl_idname = 'VIOFCD'
    bl_label = 'FloVi ControlDict socket'

    valid = ['FloVi Control']
    link_limit = 1

    def draw(self, context, layout, node, text):
        layout.label(text)

    def draw_color(self, context, node):
        return (0.5, 1.0, 0.0, 0.75)

class ViFloCdNode(bpy.types.Node, ViNodes):
    '''Openfoam Controldict export node'''
    bl_idname = 'VIOFCdn'
    bl_label = 'FloVi ControlDict'
    bl_icon = 'LAMP'
    controlD = bpy.props.StringProperty()

    def nodeupdate(self, context):
        nodecolour(self, self['exportstate'] != [str(x) for x in (self.solver)])

    solver = bpy.props.EnumProperty(items = [('simpleFoam', 'SimpleFoam', 'Steady state turbulence solver'), ('icoFoam', 'IcoFoam', 'Transient laminar solver'),
                                               ('pimpleFoam', 'PimpleFoam', 'Transient turbulence solver') ], name = "", default = 'simpleFoam', update = nodeupdate)

    def init(self, context):
        self['exportstate'] = ''
        self['nodeid'] = nodeid(self)
        self.outputs.new('VIOFCDS', 'Control out')
        nodecolour(self, 1)

    def draw_buttons(self, context, layout):
        newrow(layout, 'Solver', self, 'solver')

class ViBMExNode(bpy.types.Node, ViNodes):
    '''Openfoam blockmesh export node'''
    bl_idname = 'ViBMExNode'
    bl_label = 'FloVi BlockMesh'
    bl_icon = 'LAMP'

    solver = bpy.props.EnumProperty(items = [('icoFoam', 'IcoFoam', 'Transient laminar solver')], name = "", default = 'icoFoam')
    turbulence  = bpy.props.StringProperty()

    def nodeupdate(self, context):
        nodecolour(self, self['exportstate'] != [str(x) for x in (self.bm_xres, self.bm_yres, self.bm_zres, self.bm_xgrad, self.bm_ygrad, self.bm_zgrad)])

    bm_xres = bpy.props.IntProperty(name = "X", description = "Blockmesh X resolution", min = 0, max = 1000, default = 10, update = nodeupdate)
    bm_yres = bpy.props.IntProperty(name = "Y", description = "Blockmesh Y resolution", min = 0, max = 1000, default = 10, update = nodeupdate)
    bm_zres = bpy.props.IntProperty(name = "Z", description = "Blockmesh Z resolution", min = 0, max = 1000, default = 10, update = nodeupdate)
    bm_xgrad = bpy.props.FloatProperty(name = "X", description = "Blockmesh X simple grading", min = 0, max = 10, default = 1, update = nodeupdate)
    bm_ygrad = bpy.props.FloatProperty(name = "Y", description = "Blockmesh Y simple grading", min = 0, max = 10, default = 1, update = nodeupdate)
    bm_zgrad = bpy.props.FloatProperty(name = "Z", description = "Blockmesh Z simple grading", min = 0, max = 10, default = 1, update = nodeupdate)
    existing =  bpy.props.BoolProperty(name = '', default = 0)

    def init(self, context):
        self['exportstate'] = ''
        self['nodeid'] = nodeid(self)
        self.outputs.new('VIOfM', 'Mesh out')
        nodecolour(self, 1)

    def draw_buttons(self, context, layout):
        split = layout.split()
        col = split.column(align=True)
        col.label(text="Cell resolution:")
        col.prop(self, "bm_xres")
        col.prop(self, "bm_yres")
        col.prop(self, "bm_zres")
        col = split.column(align=True)
        col.label(text="Cell grading:")
        col.prop(self, "bm_xgrad")
        col.prop(self, "bm_ygrad")
        col.prop(self, "bm_zgrad")
        row = layout.row()
        row.operator("node.blockmesh", text = "Export").nodeid = self['nodeid']
        if not self.use_custom_color:
            newrow(layout, 'Use existing', self, 'existing')

    def update(self):
        socklink(self.outputs['Mesh out'], self['nodeid'].split('@')[1])

    def export(self):
        self.exportstate = [str(x) for x in (self.bm_xres, self.bm_yres, self.bm_zres, self.bm_xgrad, self.bm_ygrad, self.bm_zgrad)]
        nodecolour(self, 0)

class ViSHMExNode(bpy.types.Node, ViNodes):
    '''Openfoam blockmesh export node'''
    bl_idname = 'ViSHMExNode'
    bl_label = 'FloVi SnappyHexMesh'
    bl_icon = 'LAMP'
    laytypedict = {'0': (('First', 'frlayer'), ('Overall', 'olayer')), '1': (('First', 'frlayer'), ('Expansion', 'expansion')), '2': (('Final', 'fnlayer'), ('Expansion', 'expansion')),
                     '3': (('Final', 'fnlayer'), ('Overall', 'olayer')), '4': (('Final:', 'fnlayer'), ('Expansion:', 'expansion')), '5': (('Overall:', 'olayer'), ('Expansion:', 'expansion'))}

    def nodeupdate(self, context):
        nodecolour(self, self['exportstate'] != [str(x) for x in (self.lcells, self.gcells)])

    lcells = bpy.props.IntProperty(name = "", description = "SnappyhexMesh local cells", min = 0, max = 100000, default = 1000, update = nodeupdate)
    gcells = bpy.props.IntProperty(name = "", description = "SnappyhexMesh global cells", min = 0, max = 1000000, default = 10000, update = nodeupdate)
    level = bpy.props.IntProperty(name = "", description = "SnappyhexMesh level", min = 0, max = 6, default = 2, update = nodeupdate)
    surflmin = bpy.props.IntProperty(name = "", description = "SnappyhexMesh level", min = 0, max = 6, default = 2, update = nodeupdate)
    surflmax = bpy.props.IntProperty(name = "", description = "SnappyhexMesh level", min = 0, max = 6, default = 2, update = nodeupdate)
    ncellsbl = bpy.props.IntProperty(name = "", description = "Number of cells between levels", min = 0, max = 6, default = 2, update = nodeupdate)
    layers = bpy.props.IntProperty(name = "", description = "Layer number", min = 0, max = 10, default = 0, update = nodeupdate)

    layerspec = bpy.props.EnumProperty(items = [('0', 'First & overall', 'First layer thickness and overall thickness'), ('1', 'First & ER', 'First layer thickness and expansion ratio'),
                                               ('2', 'Final & ER', 'Final layer thickness and expansion ratio'), ('3', 'Final & overall', 'Final layer thickness and overall thickness'),
                                                ('4', 'Final & ER', 'Final layer thickness and expansion ratio'), ('5', 'Overall & ER', 'Overall thickness and expansion ratio')], name = "", default = '0', update = nodeupdate)
    expansion = bpy.props.FloatProperty(name = "", description = "Exapnsion ratio", min = 1.0, max = 3.0, default = 1.0, update = nodeupdate)
    llayer = bpy.props.FloatProperty(name = "", description = "Last layer thickness", min = 0.01, max = 3.0, default = 1.0, update = nodeupdate)
    frlayer = bpy.props.FloatProperty(name = "", description = "First layer thickness", min = 0.01, max = 3.0, default = 1.0, update = nodeupdate)
    fnlayer = bpy.props.FloatProperty(name = "", description = "First layer thickness", min = 0.01, max = 3.0, default = 1.0, update = nodeupdate)
    olayer = bpy.props.FloatProperty(name = "", description = "Overall layer thickness", min = 0.01, max = 3.0, default = 1.0, update = nodeupdate)

    def init(self, context):
        self['exportstate'] = ''
        self['nodeid'] = nodeid(self)
        self.inputs.new('VIOfM', 'Mesh in')
        self.outputs.new('VIOfM', 'Mesh out')
        nodecolour(self, 1)

    def draw_buttons(self, context, layout):
        newrow(layout, 'Local cells:', self, 'lcells')
        newrow(layout, 'Global cells:', self, 'gcells')
        newrow(layout, 'Level:', self, 'level')
        newrow(layout, 'Max level:', self, 'surflmax')
        newrow(layout, 'Min level:', self, 'surflmin')
        newrow(layout, 'CellsBL:', self, 'ncellsbl')
        newrow(layout, 'Layers:', self, 'layers')
        if self.layers:
            newrow(layout, 'Layer spec:', self, 'layerspec')
            [newrow(layout, laytype[0], self, laytype[1]) for laytype in self.laytypedict[self.layerspec]]
#                newrow(layout, laytype[0], self, laytype[1])
        row = layout.row()
        row.operator("node.snappy", text = "Export").nodeid = self['nodeid']

    def export(self):
        self.exportstate = [str(x) for x in (self.lcells, self.gcells)]
        nodecolour(self, 0)

class ViFVSimNode(bpy.types.Node, ViNodes):
    '''Openfoam blockmesh export node'''
    bl_idname = 'ViFVSimNode'
    bl_label = 'FloVi Simulationh'
    bl_icon = 'LAMP'

    p = bpy.props.StringProperty()
    U = bpy.props.StringProperty()
    k = bpy.props.StringProperty()
    episilon = bpy.props.StringProperty()
    omega = bpy.props.StringProperty()
    nut = bpy.props.StringProperty()
    nuTilda = bpy.props.StringProperty()

    def nodeupdate(self, context):
        context.scene['viparams']['fvsimnode'] = nodeid(self)
        nodecolour(self, self['exportstate'] != [str(x) for x in (self.solver, self.dt, self.et, self.bouyancy, self.radiation, self.turbulence)])

    solver = bpy.props.EnumProperty(items = [('simpleFoam', 'SimpleFoam', 'Steady state turbulence solver'),
                                              ('icoFoam', 'IcoFoam', 'Transient laminar solver'),
                                               ('pimpleFoam', 'PimpleFoam', 'Transient turbulence solver') ], name = "", default = 'simpleFoam', update = nodeupdate)
    dt = bpy.props.FloatProperty(name = "", description = "Simulation delta T", min = 0.001, max = 500, default = 50, update = nodeupdate)
    et = bpy.props.FloatProperty(name = "", description = "Simulation end time", min = 0.001, max = 5000, default = 500, update = nodeupdate)
    pval = bpy.props.FloatProperty(name = "", description = "Simulation delta T", min = -500, max = 500, default = 0.0, update = nodeupdate)
    uval = bpy.props.FloatVectorProperty(size = 3, name = '', attr = 'Velocity', default = [0, 0, 0], unit = 'VELOCITY', subtype = 'VELOCITY', min = -100, max = 100)
    bouyancy =  bpy.props.BoolProperty(name = '', default = 0, update=nodeupdate)
    radiation =  bpy.props.BoolProperty(name = '', default = 0, update=nodeupdate)
    turbulence =  bpy.props.EnumProperty(items = [('laminar', 'Laminar', 'Steady state turbulence solver'),
                                              ('kEpsilon', 'k-Epsilon', 'Transient laminar solver'),
                                               ('kOmega', 'k-Omega', 'Transient turbulence solver'), ('SpalartAllmaras', 'Spalart-Allmaras', 'Spalart-Allmaras turbulence solver')], name = "", default = 'laminar', update = nodeupdate)
    nutval = bpy.props.FloatProperty(name = "", description = "Simulation delta T", min = 0.0, max = 500, default = 0.0, update = nodeupdate)
    nutildaval = bpy.props.FloatProperty(name = "", description = "Simulation delta T", min = 0.0, max = 500, default = 0.0, update = nodeupdate)
    kval = bpy.props.FloatProperty(name = "", description = "Simulation delta T", min = 0.1, max = 500, default = 0.0, update = nodeupdate)
    epval = bpy.props.FloatProperty(name = "", description = "Simulation delta T", min = 0.1, max = 500, default = 0.1, update = nodeupdate)
    oval = bpy.props.FloatProperty(name = "", description = "Simulation delta T", min = 0.1, max = 500, default = 0.1, update = nodeupdate)
    convergence = bpy.props.FloatProperty(name = "", description = "Convergence criteria", min = 0.0001, max = 0.01, default = 0.0001, update = nodeupdate)

    def init(self, context):
        self['exportstate'] = ''
        self['nodeid'] = nodeid(self)
        self.inputs.new('VIOfM', 'Mesh in')
        nodecolour(self, 1)

    def draw_buttons(self, context, layout):
        newrow(layout, 'Solver:', self, 'solver')
        newrow(layout, 'deltaT:', self, 'dt')
        newrow(layout, 'End time:', self, 'et')
        newrow(layout, 'Pressure:', self, 'pval')
        newrow(layout, 'Velocity:', self, 'uval')
        if self.solver in ('simpleFoam', 'pimpleFoam'):
            newrow(layout, 'Turbulence:', self, 'turbulence')
            newrow(layout, 'Bouyancy:', self, 'bouyancy')
            newrow(layout, 'Radiation:', self, 'radiation')
            if self.turbulence != 'laminar':
                newrow(layout, 'nut value:', self, 'nutval')
                if self.turbulence == 'SpalartAllmaras':
                    newrow(layout, 'nuTilda value:', self, 'nutildaval')
                elif self.turbulence == 'kEpsilon':
                    newrow(layout, 'k value:', self, 'kval')
                    newrow(layout, 'epsilon value:', self, 'epval')
                elif self.turbulence == 'kOmega':
                    newrow(layout, 'k value:', self, 'kval')
                    newrow(layout, 'omega value:', self, 'oval')
        newrow(layout, 'Convergence:', self, 'convergence')

        row = layout.row()
        row.operator("node.fvsolve", text = "Calculate").nodeid = self['nodeid']

    def update(self):
        socklink(self.outputs['Mesh out'], self['nodeid'].split('@')[1])

    def export(self):
        self.exportstate = [str(x) for x in (self.solver, self.dt, self.et, self.bouyancy, self.radiation, self.turbulence)]
        nodecolour(self, 0)
####################### Vi Nodes Catagories ##############################

viexnodecat = [NodeItem("ViGExLiNode", label="LiVi Geometry"), NodeItem("LiViNode", label="LiVi Context"),
                NodeItem("ViGExEnNode", label="EnVi Geometry"), NodeItem("ViExEnNode", label="EnVi Context"), NodeItem("ViFloCdNode", label="FloVi Control"),
                 NodeItem("ViBMExNode", label="FloVi BlockMesh"), NodeItem("ViSHMExNode", label="FloVi SnappyHexMesh")]
                
vifilenodecat = [NodeItem("ViTextEdit", label="Text Edit")]
vinodecat = [NodeItem("ViSPNode", label="VI-Suite sun path"), NodeItem("ViSSNode", label="VI-Suite shadow study"), NodeItem("ViWRNode", label="VI-Suite wind rose"), 
             NodeItem("ViLiSNode", label="LiVi Simulation"), NodeItem("ViEnSimNode", label="EnVi Simulation"), NodeItem("ViFVSimNode", label="FloVi Simulation")]

vigennodecat = [NodeItem("ViGenNode", label="VI-Suite Generative"), NodeItem("ViTarNode", label="VI-Suite Target")]

vidisnodecat = [NodeItem("ViChNode", label="VI-Suite Chart")]
vioutnodecat = [NodeItem("ViCSV", label="VI-Suite CSV"), NodeItem("ViText", label="VI-Suite Text"), NodeItem("ViLiINode", label="LiVi Image"), NodeItem("ViLiFCNode", label="LiVi FC Image")]
viinnodecat = [NodeItem("ViLoc", label="VI Location"), NodeItem("ViEnInNode", label="EnergyPlus input file"), NodeItem("ViEnRFNode", label="EnergyPlus result file"), 
               NodeItem("ViASCImport", label="Import ESRI Grid file")]

vinode_categories = [ViNodeCategory("Output", "Output Nodes", items=vioutnodecat), ViNodeCategory("Edit", "Edit Nodes", items=vifilenodecat), ViNodeCategory("Display", "Display Nodes", items=vidisnodecat), ViNodeCategory("Generative", "Generative Nodes", items=vigennodecat), ViNodeCategory("Analysis", "Analysis Nodes", items=vinodecat), ViNodeCategory("Process", "Process Nodes", items=viexnodecat), ViNodeCategory("Input", "Input Nodes", items=viinnodecat)]


####################### EnVi ventilation network ##############################

class EnViNetwork(bpy.types.NodeTree):
    '''A node tree for the creation of EnVi advanced ventilation networks.'''
    bl_idname = 'EnViN'
    bl_label = 'EnVi Network'
    bl_icon = 'FORCE_WIND'
    nodetypes = {}

class EnViNodes:
    @classmethod
    def poll(cls, ntree):
        return ntree.bl_idname == 'EnViN'

class EnViBoundSocket(bpy.types.NodeSocket):
    '''A plain zone boundary socket'''
    bl_idname = 'EnViBoundSocket'
    bl_label = 'Plain zone boundary socket'
    bl_color = (1.0, 1.0, 0.2, 0.5)

    valid = ['Boundary']
    sn = bpy.props.StringProperty()
    uvalue = bpy.props.StringProperty()

    def draw(self, context, layout, node, text):
        layout.label(text)

    def draw_color(self, context, node):
        return (0.5, 0.2, 0.0, 0.75)

class EnViSchedSocket(bpy.types.NodeSocket):
    '''Fraction schedule socket'''
    bl_idname = 'EnViSchedSocket'
    bl_label = 'Schedule socket'
    bl_color = (1.0, 1.0, 0.0, 0.75)

    valid = ['Schedule']
    schedule = ['Fraction']

    def draw(self, context, layout, node, text):
        layout.label(text)

    def draw_color(self, context, node):
        return (1.0, 1.0, 0.0, 0.75)

class EnViTSchedSocket(bpy.types.NodeSocket):
    '''Temperature schedule socket'''
    bl_idname = 'EnViTSchedSocket'
    bl_label = 'Schedule socket'
    bl_color = (1.0, 1.0, 0.0, 0.75)

    valid = ['Schedule']
    schedule = ['Temperature']

    def draw(self, context, layout, node, text):
        layout.label(text)

    def draw_color(self, context, node):
        return (1.0, 1.0, 0.0, 0.75)

class EnViSSFlowSocket(bpy.types.NodeSocket):
    '''A sub-surface flow socket'''
    bl_idname = 'EnViSSFlowSocket'
    bl_label = 'Sub-surface flow socket'

    sn = bpy.props.StringProperty()
    valid = ['Sub-surface']

    def draw(self, context, layout, node, text):
        layout.label(text)

    def draw_color(self, context, node):
        return (0.1, 1.0, 0.2, 0.75)

class EnViSFlowSocket(bpy.types.NodeSocket):
    '''A surface flow socket'''
    bl_idname = 'EnViSFlowSocket'
    bl_label = 'Surface flow socket'

    sn = bpy.props.StringProperty()
    valid = ['Surface']

    def draw(self, context, layout, node, text):
        layout.label(text)

    def draw_color(self, context, node):
        return (1.0, 0.2, 0.2, 0.75)

class EnViSSSFlowSocket(bpy.types.NodeSocket):
    '''A surface or sub-surface flow socket'''
    bl_idname = 'EnViSSSFlowSocket'
    bl_label = '(Sub-)Surface flow socket'

    sn = bpy.props.StringProperty()
    valid = ['(Sub)Surface']

    def draw(self, context, layout, node, text):
        layout.label(text)

    def draw_color(self, context, node):
        return (1.0, 1.0, 0.2, 0.75)

class EnViCrRefSocket(bpy.types.NodeSocket):
    '''A plain zone airflow component socket'''
    bl_idname = 'EnViCrRefSocket'
    bl_label = 'Plain zone airflow component socket'

    sn = bpy.props.StringProperty()

    def draw(self, context, layout, node, text):
        layout.label(text)

    def draw_color(self, context, node):
        return (1.0, 0.4, 0.0, 0.75)

class EnViOccSocket(bpy.types.NodeSocket):
    '''An EnVi zone occupancy socket'''
    bl_idname = 'EnViOccSocket'
    bl_label = 'Zone occupancy socket'

    sn = bpy.props.StringProperty()
    valid = ['Occupancy']

    def draw(self, context, layout, node, text):
        layout.label(text)

    def draw_color(self, context, node):
        return (1.0, 0.2, 0.2, 0.75)

class EnViEqSocket(bpy.types.NodeSocket):
    '''An EnVi zone equipment socket'''
    bl_idname = 'EnViEqSocket'
    bl_label = 'Zone equipment socket'

    sn = bpy.props.StringProperty()
    valid = ['Equipment']

    def draw(self, context, layout, node, text):
        layout.label(text)

    def draw_color(self, context, node):
        return (1.0, 0.2, 0.2, 0.75)

class EnViInfSocket(bpy.types.NodeSocket):
    '''An EnVi zone infiltration socket'''
    bl_idname = 'EnViInfSocket'
    bl_label = 'Zone infiltration socket'

    valid = ['Infiltration']

    def draw(self, context, layout, node, text):
        layout.label(text)

    def draw_color(self, context, node):
        return (1.0, 0.2, 0.2, 0.75)

class EnViHvacSocket(bpy.types.NodeSocket):
    '''An EnVi zone HVAC socket'''
    bl_idname = 'EnViHvacSocket'
    bl_label = 'Zone HVAC socket'

    sn = bpy.props.StringProperty()
    valid = ['HVAC']

    def draw(self, context, layout, node, text):
        layout.label(text)

    def draw_color(self, context, node):
        return (1.0, 0.2, 0.2, 0.75)

class EnViWPCSocket(bpy.types.NodeSocket):
    '''An EnVi external node WPC socket'''
    bl_idname = 'EnViWPCSocket'
    bl_label = 'External node WPC'

    sn = bpy.props.StringProperty()
    valid = ['WPC']

    def draw(self, context, layout, node, text):
        layout.label(text)

    def draw_color(self, context, node):
        return (0.2, 0.2, 0.2, 0.75)

class EnViActSocket(bpy.types.NodeSocket):
    '''An EnVi actuator socket'''
    bl_idname = 'EnViActSocket'
    bl_label = 'EnVi actuator socket'

    sn = bpy.props.StringProperty()
    valid = ['Actuator']

    def draw(self, context, layout, node, text):
        layout.label(text)

    def draw_color(self, context, node):
        return (0.2, 0.9, 0.9, 0.75)

class EnViSenseSocket(bpy.types.NodeSocket):
    '''An EnVi sensor socket'''
    bl_idname = 'EnViSenseSocket'
    bl_label = 'EnVi sensor socket'

    sn = bpy.props.StringProperty()
    valid = ['Sensor']

    def draw(self, context, layout, node, text):
        layout.label(text)

    def draw_color(self, context, node):
        return (0.9, 0.9, 0.2, 0.75)

class AFNCon(bpy.types.Node, EnViNodes):
    '''Node defining the overall airflow network simulation'''
    bl_idname = 'AFNCon'
    bl_label = 'Control'
    bl_icon = 'SOUND'

    def wpcupdate(self, context):
        if self.wpctype == 'SurfaceAverageCalculation':
            if self.inputs['WPC Array'].is_linked:
                remlink(self, self.inputs['WPC Array'].links)
            self.inputs['WPC Array'].hide = True
        elif self.wpctype == 'Input':
            self.inputs['WPC Array'].hide = False
        self.legal()

    afnname = bpy.props.StringProperty(name = '')
    afntype = bpy.props.EnumProperty(items = [('MultizoneWithDistribution', 'MultizoneWithDistribution', 'Include a forced airflow system in the model'),
                                              ('MultizoneWithoutDistribution', 'MultizoneWithoutDistribution', 'Exclude a forced airflow system in the model'),
                                              ('MultizoneWithDistributionOnlyDuringFanOperation', 'MultizoneWithDistributionOnlyDuringFanOperation', 'Apply forced air system only when in operation'),
                                              ('NoMultizoneOrDistribution', 'NoMultizoneOrDistribution', 'Only zone infiltration controls are modelled')], name = "", default = 'MultizoneWithoutDistribution')

    wpctype = bpy.props.EnumProperty(items = [('SurfaceAverageCalculation', 'SurfaceAverageCalculation', 'Calculate wind pressure coefficients based on oblong building assumption'),
                                              ('Input', 'Input', 'Input wind pressure coefficients from an external source')], name = "", default = 'SurfaceAverageCalculation', update = wpcupdate)
    wpcaname = bpy.props.StringProperty()
    wpchs = bpy.props.EnumProperty(items = [('OpeningHeight', 'OpeningHeight', 'Calculate wind pressure coefficients based on opening height'),
                                              ('ExternalNode', 'ExternalNode', 'Calculate wind pressure coefficients based on external node height')], name = "", default = 'OpeningHeight')
    buildtype = bpy.props.EnumProperty(items = [('LowRise', 'Low Rise', 'Height is less than 3x the longest wall'),
                                              ('HighRise', 'High Rise', 'Height is more than 3x the longest wall')], name = "", default = 'LowRise')

    maxiter = bpy.props.IntProperty(default = 500, description = 'Maximum Number of Iterations', name = "")

    initmet = bpy.props.EnumProperty(items = [('ZeroNodePressures', 'ZeroNodePressures', 'Initilisation type'),
                                              ('LinearInitializationMethod', 'LinearInitializationMethod', 'Initilisation type')], name = "", default = 'ZeroNodePressures')
    rcontol = bpy.props.FloatProperty(default = 0.0001, description = 'Relative Airflow Convergence Tolerance', name = "")
    acontol = bpy.props.FloatProperty(min = 0.000001, max = 0.1, default = 0.000001, description = 'Absolute Airflow Convergence Tolerance', name = "")
    conal = bpy.props.FloatProperty(default = -0.1, max = 1, min = -1, description = 'Convergence Acceleration Limit', name = "")
    aalax = bpy.props.IntProperty(default = 0, max = 180, min = 0, description = 'Azimuth Angle of Long Axis of Building', name = "")
    rsala = bpy.props.FloatProperty(default = 1, max = 1, min = 0, description = 'Ratio of Building Width Along Short Axis to Width Along Long Axis', name = "")

    def init(self, context):
        self['nodeid'] = nodeid(self)
        self.inputs.new('EnViWPCSocket', 'WPC Array')

    def draw_buttons(self, context, layout):
        yesno = (1, 1, 1, self.wpctype == 'Input', self.wpctype != 'Input' and self.wpctype == 'SurfaceAverageCalculation', 1, 1, 1, 1, 1, self.wpctype == 'SurfaceAverageCalculation', self.wpctype == 'SurfaceAverageCalculation')
        vals = (('Name:', 'afnname'), ('Type:', 'afntype'), ('WPC type:', 'wpctype'), ('WPC height', 'wpchs'), ('Build type:', 'buildtype'), ('Max iter:','maxiter'), ('Init method:', 'initmet'),
         ('Rel Converge:', 'rcontol'), ('Abs Converge:', 'acontol'), ('Converge Lim:', 'conal'), ('Azimuth:', 'aalax'), ('Axis ratio:', 'rsala'))
        [newrow(layout, val[0], self, val[1]) for v, val in enumerate(vals) if yesno[v]]

    def epwrite(self, exp_op, enng):
        wpcaentry = ''
        if self.wpctype == 'Input' and not self.inputs['WPC Array'].is_linked:
            exp_op.report({'ERROR'},"WPC array input has been selected in the control node, but no WPC array node is attached")
            return 'ERROR'

        wpcaname = 'WPC Array' if not self.wpcaname else self.wpcaname
        self.afnname = 'default' if not self.afnname else self.afnname
        wpctype = 1 if self.wpctype == 'Input' else 0
        paramvs = (self.afnname, self.afntype,
                     self.wpctype, ("", wpcaname)[wpctype], ("", self.wpchs)[wpctype], (self.buildtype, "")[wpctype], self.maxiter, self.initmet,
                    '{:.3E}'.format(self.rcontol), '{:.3E}'.format(self.acontol), '{:.3E}'.format(self.conal), (self.aalax, "")[wpctype], (self.rsala, "")[wpctype])

        params = ('Name', 'AirflowNetwork Control', 'Wind Pressure Coefficient Type', 'AirflowNetwork Wind Pressure Coefficient Array Name', \
        'Height Selection for Local Wind Pressure Calculation', 'Building Type', 'Maximum Number of Iterations (dimensionless)', 'Initialization Type', \
        'Relative Airflow Convergence Tolerance (dimensionless)', 'Absolute Airflow Convergence Tolerance (kg/s)', 'Convergence Acceleration Limit (dimensionless)', \
        'Azimuth Angle of Long Axis of Building (deg)', 'Ratio of Building Width Along Short Axis to Width Along Long Axis')

        simentry = epentry('AirflowNetwork:SimulationControl', params, paramvs)

        if self.inputs['WPC Array'].is_linked:
            (wpcaentry, enng['enviparams']['wpcn']) = self.inputs['WPC Array'].links[0].from_node.epwrite() if wpctype == 1 else ('', 0)
            enng['enviparams']['wpca'] = 1
        self.legal()
        return simentry + wpcaentry

    def update(self):
        self.legal()

    def legal(self):
        try:
            bpy.data.node_groups[self['nodeid'].split('@')[1]]['enviparams']['wpca'] = 1 if self.wpctype == 'Input' and self.inputs['WPC Array'].is_linked else 0
            nodecolour(self, self.wpctype == 'Input' and not self.inputs['WPC Array'].is_linked)
            for node in [node for node in bpy.data.node_groups[self['nodeid'].split('@')[1]].nodes if node.bl_idname in ('EnViSFlow', 'EnViSSFlow')]:
                node.legal()
        except:
            pass

class EnViWPCA(bpy.types.Node, EnViNodes):
    '''Node describing Wind Pressure Coefficient array'''
    bl_idname = 'EnViWPCA'
    bl_label = 'Envi WPCA'
    bl_icon = 'SOUND'

    (ang1, ang2, ang3, ang4, ang5, ang6, ang7, ang8, ang9, ang10, ang11, ang12) = [bpy.props.IntProperty(name = '', default = 0, min = 0, max = 360) for x in range(12)]

    def init(self, context):
        self['nodeid'] = nodeid(self)
        self.outputs.new('EnViWPCSocket', 'WPC values')

    def draw_buttons(self, context, layout):
        row = layout.row()
        row.label('WPC Angles')
        for w in range(1, 13):
            row = layout.row()
            row.prop(self, 'ang{}'.format(w))

    def update(self):
        socklink(self.outputs['WPC values'], self['nodeid'].split('@')[1])
        bpy.data.node_groups[self['nodeid'].split('@')[1]].interface_update(bpy.context)

    def epwrite(self):
        angs = (self.ang1,self.ang2, self.ang3, self.ang4, self.ang5, self.ang6, self.ang7, self.ang8, self.ang9, self.ang10, self.ang11, self.ang12)
        aparamvs = ['WPC Array'] + [wd for w, wd in enumerate(angs) if wd not in angs[:w]]
        aparams = ['Name'] + ['Wind Direction {} (deg)'.format(w + 1) for w in range(len(aparamvs) - 1)]
        return (epentry('AirflowNetwork:MultiZone:WindPressureCoefficientArray', aparams, aparamvs), len(aparamvs) - 1)

class EnViCrRef(bpy.types.Node, EnViNodes):
    '''Node describing reference crack conditions'''
    bl_idname = 'EnViCrRef'
    bl_label = 'ReferenceCrackConditions'
    bl_icon = 'SOUND'

    reft = bpy.props.FloatProperty(name = '', min = 0, max = 30, default = 20, description = 'Reference Temperature ('+u'\u00b0C)')
    refp = bpy.props.IntProperty(name = '', min = 100000, max = 105000, default = 101325, description = 'Reference Pressure (Pa)')
    refh = bpy.props.FloatProperty(name = '', min = 0, max = 10, default = 0, description = 'Reference Humidity Ratio (kgWater/kgDryAir)')

    def draw_buttons(self, context, layout):
        vals = (('Temperature:' ,'reft'), ('Pressure:', 'refp'), ('Humidity', 'refh'))
        [newrow(layout, val[0], self, val[1]) for val in vals]

    def epwrite(self):
        params = ('Name', 'Reference Temperature', 'Reference Pressure', 'Reference Humidity Ratio')
        paramvs = ('ReferenceCrackConditions', self.reft, self.refp, self.refh)
        return epentry('AirflowNetwork:MultiZone:ReferenceCrackConditions', params, paramvs)

class EnViOcc(bpy.types.Node, EnViNodes):
    '''Zone occupancy node'''
    bl_idname = 'EnViOcc'
    bl_label = 'Occupancy'
    bl_icon = 'SOUND'

    envi_occwatts = bpy.props.IntProperty(name = "W/p", description = "Watts per person", min = 1, max = 800, default = 90)
    envi_weff = bpy.props.FloatProperty(name = "", description = "Work efficiency", min = 0, max = 1, default = 0.0)
    envi_airv = bpy.props.FloatProperty(name = "", description = "Average air velocity", min = 0, max = 1, default = 0.1)
    envi_cloth = bpy.props.FloatProperty(name = "", description = "Clothing level", min = 0, max = 10, default = 0.5)
    envi_occtype = bpy.props.EnumProperty(items = [("0", "None", "No occupancy"),("1", "Occupants", "Actual number of people"), ("2", "Person/m"+ u'\u00b2', "Number of people per squared metre floor area"),
                                              ("3", "m"+ u'\u00b2'+"/Person", "Floor area per person")], name = "", description = "The type of zone occupancy specification", default = "0")
    envi_occsmax = bpy.props.FloatProperty(name = "", description = "Maximum level of occupancy that will occur in this schedule", min = 1, max = 500, default = 1)
    envi_comfort = bpy.props.BoolProperty(name = "", description = "Enable comfort calculations for this space", default = False)
    envi_co2 = bpy.props.BoolProperty(name = "", description = "Enable CO2 concentration calculations", default = False)

    def init(self, context):
        self['nodeid'] = nodeid(self)
        self.outputs.new('EnViOccSocket', 'Occupancy')
        self.inputs.new('EnViSchedSocket', 'OSchedule')
        self.inputs.new('EnViSchedSocket', 'ASchedule')
        self.inputs.new('EnViSchedSocket', 'WSchedule')
        self.inputs.new('EnViSchedSocket', 'VSchedule')
        self.inputs.new('EnViSchedSocket', 'CSchedule')

    def draw_buttons(self, context, layout):
        newrow(layout, 'Type:', self, "envi_occtype")
        if self.envi_occtype != '0':
            newrow(layout, 'Max level:', self, "envi_occsmax")
            if not self.inputs['ASchedule'].links:
                newrow(layout, 'Activity level:', self, 'envi_occwatts')
            newrow(layout, 'Comfort calc:', self, 'envi_comfort')
            if self.envi_comfort:
                if not self.inputs['WSchedule'].links:
                    newrow(layout, 'Work efficiency:', self, 'envi_weff')
                if not self.inputs['VSchedule'].links:
                    newrow(layout, 'Air velocity:', self, 'envi_airv')
                if not self.inputs['CSchedule'].links:
                    newrow(layout, 'Clothing:', self, 'envi_cloth')
                newrow(layout, 'CO2:', self, 'envi_co2')

    def update(self):
        if self.inputs.get('CSchedule'):
            for sock in  self.outputs:
                socklink(sock, self['nodeid'].split('@')[1])

    def epwrite(self, zn):
        pdict = {'0': '', '1':'People', '2': 'People/Area', '3': 'Area/Person'}
        plist = ['', '', '']
        plist[int(self.envi_occtype) - 1] = self.envi_occsmax
        params =  ['Name', 'Zone or ZoneList Name', 'Number of People Schedule Name', 'Number of People Calculation Method', 'Number of People', 'People per Zone Floor Area (person/m2)',
        'Zone Floor Area per Person (m2/person)', 'Fraction Radiant', 'Sensible Heat Fraction', 'Activity Level Schedule Name']
        paramvs = [zn + "_occupancy", zn, zn + '_occsched', pdict[self.envi_occtype]] + plist + [0.3, '', zn + '_actsched']
        if self.envi_comfort:
            params += ['Carbon Dioxide Generation Rate (m3/s-W)', 'Enable ASHRAE 55 Comfort Warnings',
                       'Mean Radiant Temperature Calculation Type', 'Surface Name/Angle Factor List Name', 'Work Efficiency Schedule Name', 'Clothing Insulation Calculation Method', 'Clothing Insulation Calculation Method Schedule Name',
                       'Clothing Insulation Schedule Name', 'Air Velocity Schedule Name', 'Thermal Comfort Model 1 Type']
            paramvs += [3.82E-8, 'No', 'zoneaveraged', '', zn + '_wesched', 'ClothingInsulationSchedule', '', zn + '_closched', zn + '_avsched', 'FANGER']
        return epentry('People', params, paramvs)

class EnViEq(bpy.types.Node, EnViNodes):
    '''Zone equipment node'''
    bl_idname = 'EnViEq'
    bl_label = 'Equipment'
    bl_icon = 'SOUND'

    envi_equiptype = bpy.props.EnumProperty(items = [("0", "None", "No equipment"),("1", "EquipmentLevel", "Overall equpiment gains"), ("2", "Watts/Area", "Equipment gains per square metre floor area"),
                                              ("3", "Watts/Person", "Equipment gains per occupant")], name = "", description = "The type of zone equipment gain specification", default = "0")
    envi_equipmax = bpy.props.FloatProperty(name = "", description = "Maximum level of equipment gain", min = 1, max = 50000, default = 1)

    def init(self, context):
        self['nodeid'] = nodeid(self)
        self.outputs.new('EnViEqSocket', 'Equipment')
        self.inputs.new('EnViSchedSocket', 'Schedule')

    def draw_buttons(self, context, layout):
        newrow(layout, 'Type:', self, "envi_equiptype")
        if self.envi_equiptype != '0':
            newrow(layout, 'Max level:', self, "envi_equipmax")

    def update(self):
        for sock in self.outputs:
            socklink(sock, self['nodeid'].split('@')[1])

    def oewrite(self, zn):
        edict = {'0': '', '1':'EquipmentLevel', '2': 'Watts/Area', '3': 'Watts/Person'}
        elist = ['', '', '']
        elist[int(self.envi_equiptype) - 1] = self.envi_equipmax
        params = ('Name', 'Fuel type', 'Zone Name', 'SCHEDULE Name', 'Design Level calculation method', 'Design Level (W)', 'Power per Zone Floor Area (Watts/m2)', 'Power per Person (Watts/person)', \
        'Fraction Latent', 'Fraction Radiant', 'Fraction Lost')
        paramvs = [zn + "_equip", 'Electricity', zn, zn + "_eqsched", edict[self.envi_equiptype]] + elist + ['0', '0', '0']
        return epentry('OtherEquipment', params, paramvs)

class EnViInf(bpy.types.Node, EnViNodes):
    '''Zone infiltration node'''
    bl_idname = 'EnViInf'
    bl_label = 'Infiltration'
    bl_icon = 'SOUND'

    envi_inftype = bpy.props.EnumProperty(items = [("0", "None", "No infiltration"), ("1", 'Flow/Zone', "Absolute flow rate in m{}/s".format(u'\u00b3')), ("2", "Flow/Area", 'Flow in m{}/s per m{} floor area'.format(u'\u00b3', u'\u00b2')),
                                 ("3", "Flow/ExteriorArea", 'Flow in m{}/s per m{} external surface area'.format(u'\u00b3', u'\u00b2')), ("4", "Flow/ExteriorWallArea", 'Flow in m{}/s per m{} external wall surface area'.format(u'\u00b3', u'\u00b2')),
                                 ("5", "ACH", "ACH flow rate")], name = "", description = "The type of zone infiltration specification", default = "0")
    unit = {'0':'', '1': '(m{}/s)'.format(u'\u00b3'), '2': '(m{}/s.m{})'.format(u'\u00b3', u'\u00b2'), '3': '(m{}/s per m{})'.format(u'\u00b3', u'\u00b2'), '4': '(m{}/s per m{})'.format(u'\u00b3', u'\u00b2'), "5": "(ACH)"}
    envi_inflevel = bpy.props.FloatProperty(name = "", description = "Level of Infiltration", min = 0, max = 500, default = 0.001)

    def init(self, context):
        self['nodeid'] = nodeid(self)
        self.outputs.new('EnViInfSocket', 'Infiltration')
        self.inputs.new('EnViSchedSocket', 'Schedule')

    def draw_buttons(self, context, layout):
        newrow(layout, 'Type:', self, "envi_inftype")
        if self.envi_inftype != '0':
            newrow(layout, 'Level {}:'.format(self.unit[self.envi_inftype]), self, "envi_inflevel")

    def update(self):
        for sock in self.outputs:
            socklink(sock, self['nodeid'].split('@')[1])

    def epwrite(self, zn):
        infildict = {'0': '', '1': 'Flow/Zone', '2': 'Flow/Area', '3': 'Flow/ExteriorArea', '4': 'Flow/ExteriorWallArea',
                          '5': 'AirChanges/Hour', '6': 'Flow/Zone'}
        inflist = ['', '', '', '']
        infdict = {'1': '0', '2': '1', '3':'2', '4':'2', '5': '3', '6': '0'}
        inflist[int(infdict[self.envi_inftype])] = '{:.4f}'.format(self.envi_inflevel)
        params = ('Name', 'Zone or ZoneList Name', 'Schedule Name', 'Design Flow Rate Calculation Method', 'Design Flow Rate {m3/s}', 'Flow per Zone Floor Area {m3/s-m2}',
               'Flow per Exterior Surface Area {m3/s-m2}', 'Air Changes per Hour {1/hr}', 'Constant Term Coefficient', 'Temperature Term Coefficient',
                'Velocity Term Coefficient', 'Velocity Squared Term Coefficient')
        paramvs = [zn + '_infiltration', zn, zn + '_infsched', infildict[self.envi_inftype]] + inflist + [1, 0, 0, 0]
        return epentry('ZoneInfiltration:DesignFlowRate', params, paramvs)

class EnViHvac(bpy.types.Node, EnViNodes):
    '''Zone HVAC node'''
    bl_idname = 'EnViHvac'
    bl_label = 'HVAC'
    bl_icon = 'SOUND'

    def hupdate(self, context):
        self.h = 1 if self.envi_hvachlt != '4' else 0
        self.c = 1 if self.envi_hvacclt != '4' else 0
        self['hc'] = ('', 'SingleHeating', 'SingleCooling', 'DualSetpoint')[(not self.h and not self.c, self.h and not self.c, not self.h and self.c, self.h and self.c).index(1)]
        
    envi_hvact = bprop("", "", False)
    envi_hvacht = fprop(u'\u00b0C', "Heating temperature:", 1, 99, 50)
    envi_hvacct = fprop(u'\u00b0C', "Cooling temperature:", -10, 20, 13)
    envi_hvachlt = bpy.props.EnumProperty(items = [('0', 'LimitFlowRate', 'LimitFlowRate'), ('1', 'LimitCapacity', 'LimitCapacity'), ('2', 'LimitFlowRateAndCapacity', 'LimitFlowRateAndCapacity'), ('3', 'NoLimit', 'NoLimit'), ('4', 'None', 'No heating')], name = '', description = "Heating limit type", default = '4', update = hupdate)
    envi_hvachaf = bpy.props.FloatProperty(name = u'm\u00b3/s', description = "Heating air flow rate", min = 0, max = 60, default = 1, precision = 4)
    envi_hvacshc = fprop("W", "Sensible heating capacity", 0, 10000, 1000)
    envi_hvacclt = bpy.props.EnumProperty(items = [('0', 'LimitFlowRate', 'LimitFlowRate'), ('1', 'LimitCapacity', 'LimitCapacity'), ('2', 'LimitFlowRateAndCapacity', 'LimitFlowRateAndCapacity'), ('3', 'NoLimit', 'NoLimit'), ('4', 'None', 'No cooling')], name = '', description = "Cooling limit type", default = '4', update = hupdate)
    envi_hvaccaf = bpy.props.FloatProperty(name = u'm\u00b3/s', description = "Cooling air flow rate", min = 0, max = 60, default = 1, precision = 4)
    envi_hvacscc = fprop("W", "Sensible cooling capacity", 0, 10000, 1000)
    envi_hvacoam = eprop([('0', 'None', 'None'), ('1', 'Flow/Zone', 'Flow/Zone'), ('2', 'Flow/Person', 'Flow/Person'), ('3', 'Flow/Area', 'Flow/Area'), ('4', 'Sum', 'Sum'), ('5', 'Maximum ', 'Maximum'), ('6', 'ACH/Detailed', 'ACH/Detailed')], '', "Cooling limit type", '2')
    envi_hvacfrp = fprop(u'm\u00b3/s/p', "Flow rate per person", 0, 1, 0.008)
    envi_hvacfrzfa = fprop("", "Flow rate per zone area", 0, 1, 0.008)
    envi_hvacfrz = bpy.props.FloatProperty(name = u'm\u00b3/s', description = "Flow rate per zone", min = 0, max = 100, default = 0.1, precision = 4)
    envi_hvacfach = fprop("", "ACH", 0, 10, 1)
    envi_hvachr = eprop([('0', 'None', 'None'), ('1', 'Sensible', 'Flow/Zone')], '', "Heat recovery type", '0')
    envi_hvachre = fprop("", "Heat recovery efficiency", 0, 1, 0.7)
    h = iprop('', '', 0, 1, 0)
    c = iprop('', '', 0, 1, 0)
    actlist = [("0", "Air supply temp", "Actuate an ideal air load system supply temperature"), ("1", "Air supply flow", "Actuate an ideal air load system flow rate"),
               ("2", "Outdoor Air supply flow", "Actuate an ideal air load system outdoor air flow rate")]
    acttype = bpy.props.EnumProperty(name="", description="Actuator type", items=actlist, default='0')
    compdict = {'0': 'AirFlow Network Window/Door Opening'}
    actdict =  {'0': ('Venting Opening Factor', 'of')}
    envi_heat = bpy.props.BoolProperty(name = "Heating", description = 'Turn on zone heating', default = 0)
    envi_htsp = bpy.props.FloatProperty(name = u'\u00b0C', description = "Temperature", min = 0, max = 50, default = 20)
    envi_cool = bpy.props.BoolProperty(name = "Cooling", description = "Turn on zone cooling", default = 0)
    envi_ctsp = bpy.props.FloatProperty(name = u'\u00b0'+"C", description = "Temperature", min = 0, max = 50, default = 20)

    def init(self, context):
        self['nodeid'] = nodeid(self)
        self['hc'] = ''
        self['ctdict'] = {'DualSetpoint': 4, 'SingleHeating': 1, 'SingleCooling': 2}
        self['limittype'] = {'0': 'LimitFlowRate', '1': 'LimitCapacity', '2': 'LimitFlowRateAndCapacity', '3': 'NoLimit', '4': ''}
        self.outputs.new('EnViHvacSocket', 'HVAC')
        self.inputs.new('EnViSchedSocket', 'Schedule')
        self.inputs.new('EnViTSchedSocket', 'HSchedule')
        self.inputs.new('EnViTSchedSocket', 'CSchedule')

    def draw_buttons(self, context, layout):
        row = layout.row()
        row.label('HVAC Template:')
        row.prop(self, 'envi_hvact')
        row = layout.row()
        row.label('Heating -----------')
        newrow(layout, 'Heating limit:', self, 'envi_hvachlt')
        if self.envi_hvachlt != '4':
            newrow(layout, 'Heating temp:', self, 'envi_hvacht')
            if self.envi_hvachlt in ('0', '2',):
                newrow(layout, 'Heating airflow:', self, 'envi_hvachaf')
            if self.envi_hvachlt in ('1', '2'):
                newrow(layout, 'Heating capacity:', self, 'envi_hvacshc')
            if not self.inputs['HSchedule'].links:
                newrow(layout, 'Thermostat level:', self, 'envi_htsp')
            newrow(layout, 'Heat recovery:', self, 'envi_hvachr')
            if self.envi_hvachr != '0':
                newrow(layout, 'HR eff.:', self, 'envi_hvachre')

        row = layout.row()
        row.label('Cooling ------------')
        newrow(layout, 'Cooling limit:', self, 'envi_hvacclt')
        if self.envi_hvacclt != '4':
            newrow(layout, 'Cooling temp:', self, 'envi_hvacct')
            if self.envi_hvacclt in ('0', '2'):
                newrow(layout, 'Cooling airflow:', self, 'envi_hvaccaf')
            if self.envi_hvacclt in ('1', '2'):
                newrow(layout, 'Cooling capacity:', self, 'envi_hvacscc')
            if not self.inputs['CSchedule'].links:
                newrow(layout, 'Thermostat level:', self, 'envi_ctsp')

        if (self.envi_hvachlt, self.envi_hvacclt) != ('4', '4'):
            row = layout.row()
            row.label('Outdoor air --------------')
            newrow(layout, 'Outdoor air:', self, 'envi_hvacoam')
            if self.envi_hvacoam in ('2', '4', '5'):
                newrow(layout, 'Flow/person:', self, 'envi_hvacfrp')
            if self.envi_hvacoam in ('1', '4', '5'):
                newrow(layout, 'Zone flow:', self, 'envi_hvacfrz')
            if self.envi_hvacoam in ('3', '4', '5'):
                newrow(layout, 'Flow/area:', self, 'envi_hvacfrzfa')
            if self.envi_hvacoam in ('4', '5', '6') and not self.envi_hvact:
                newrow(layout, 'ACH', self, 'envi_hvacfach')

    def update(self):
        for sock in self.outputs:
            socklink(sock, self['nodeid'].split('@')[1])
    
    def eptcwrite(self, zn):
        if self['hc'] in ('SingleHeating', 'SingleCooling', 'DualSetpoint'):
            return epschedwrite(zn + '_thermocontrol', 'Control Type', ['Through: 12/31'], [['For: Alldays']], [[[['Until: 24:00,{}'.format(self['ctdict'][self['hc']])]]]])
        else:
            return ''
            
    def eptspwrite(self, zn):
        params = ['Name', 'Setpoint Temperature Schedule Name']
        if self['hc'] ==  'DualSetpoint':
            params += ['Setpoint Temperature Schedule Name 2']
            paramvs = [zn +'_tsp', zn + '_htspsched', zn + '_ctspsched']
        elif self['hc'] == 'SingleHeating':
            paramvs = [zn +'_tsp', zn + '_htspsched']
        elif self['hc'] == 'SingleCooling':
            paramvs = [zn +'_tsp', zn + '_ctspsched']

        if self['hc'] in ('SingleHeating', 'SingleCooling', 'DualSetpoint'):
            params2 = ('Name', 'Zone or Zonelist Name', 'Control Type Schedule Name', 'Control 1 Object Type', 'Control 1 Name')
            paramvs2 = (zn+'_thermostat', zn, zn +'_thermocontrol', 'ThermostatSetpoint:{}'.format(self['hc']), zn + '_tsp')
            return epentry('ThermostatSetpoint:{}'.format(self['hc']), params, paramvs) + epentry('ZoneControl:Thermostat', params2, paramvs2)
        else:
            return ''

    def ephwrite(self, zn):
        params = ('Name', 'Availability Schedule Name', 'Zone Supply Air Node Name', 'Zone Exhaust Air Node Name',
              "Maximum Heating Supply Air Temperature (degC)", "Minimum Cooling Supply Air Temperature (degC)",
              'Maximum Heating Supply Air Humidity Ratio (kgWater/kgDryAir)', 'Minimum Cooling Supply Air Humidity Ratio (kgWater/kgDryAir)',
              'Heating Limit', 'Maximum Heating Air Flow Rate (m3/s)', 'Maximum Sensible Heating Capacity (W)',
              'Cooling limit', 'Maximum Cooling Air Flow Rate (m3/s)', 'Maximum Total Cooling Capacity (W)', 'Heating Availability Schedule Name',
              'Cooling Availability Schedule Name', 'Dehumidification Control Type', 'Cooling Sensible Heat Ratio (dimensionless)', 'Humidification Control Type',
              'Design Specification Outdoor Air Object Name', 'Outdoor Air Inlet Node Name', 'Demand Controlled Ventilation Type', 'Outdoor Air Economizer Type',
              'Heat Recovery Type', 'Sensible Heat Recovery Effectiveness (dimensionless)', 'Latent Heat Recovery Effectiveness (dimensionless)')
        paramvs = ('{}_Air'.format(zn), zn + '_hvacsched', '{}_supairnode'.format(zn), '', self.envi_hvacht, self.envi_hvacct, 0.015, 0.009, self['limittype'][self.envi_hvachlt],
                   '{:.4f}'.format(self.envi_hvachaf) if self.envi_hvachlt in ('0', '2') else '', self.envi_hvacshc if self.envi_hvachlt in ('1', '2') else '', self['limittype'][self.envi_hvacclt],
                   '{:.4f}'.format(self.envi_hvaccaf) if self.envi_hvacclt in ('0', '2') else '', self.envi_hvacscc if self.envi_hvacclt in ('1', '2') else '',
                   '', '', 'ConstantSupplyHumidityRatio', '', 'ConstantSupplyHumidityRatio', (zn + ' Outdoor Air', '')[self.envi_hvacoam == '0'], '', '', '', ('None', 'Sensible')[int(self.envi_hvachr)], self.envi_hvachre, '')
        entry = epentry('ZoneHVAC:IdealLoadsAirSystem', params, paramvs)

        if self.envi_hvacoam != '0':
            oam = {'0':'None', '1':'Flow/Zone', '2':'Flow/Person', '3':'Flow/Area', '4':'Sum', '5':'Maximum', '6':'AirChanges/Hour'}
            params2 = ('Name', 'Outdoor Air  Method', 'Outdoor Air Flow per Person (m3/s)', 'Outdoor Air Flow per Zone Floor Area (m3/s-m2)', 'Outdoor Air  Flow per Zone',
            'Outdoor Air Flow Air Changes per Hour', 'Outdoor Air Flow Rate Fraction Schedule Name')
            paramvs2 =(zn + ' Outdoor Air', oam[self.envi_hvacoam], '{:.4f}'.format(self.envi_hvacfrp) if self.envi_hvacoam in ('2', '4', '5') else '',
                        '{:.4f}'.format(self.envi_hvacfrzfa) if self.envi_hvacoam in ('3', '4', '5') else '', '{:.4f}'.format(self.envi_hvacfrz) if self.envi_hvacoam in ('1', '4', '5') else '',
                        '{:.4f}'.format(self.envi_hvacfach) if self.envi_hvacoam in ('4', '5', '6') else '', '')
            entry += epentry('DesignSpecification:OutdoorAir', params2, paramvs2)
        return entry

    def hvactwrite(self, zn):
        self.hupdate()
        oam = {'0':'None', '1':'Flow/Zone', '2':'Flow/Person', '3':'Flow/Area', '4':'Sum', '5':'Maximum', '6':'DetailedSpecification'}
        params = ('Zone Name' , 'Thermostat Name', 'System Availability Schedule Name', 'Maximum Heating Supply Air Temperature', 'Minimum Cooling Supply Air Temperature',
                'Maximum Heating Supply Air Humidity Ratio (kgWater/kgDryAir)', 'Minimum Cooling Supply Air Humidity Ratio (kgWater/kgDryAir)', 'Heating Limit', 'Maximum Heating Air Flow Rate (m3/s)',
                'Maximum Sensible Heating Capacity (W)', 'Cooling Limit', 'Maximum Cooling Air Flow Rate (m3/s)', 'Maximum Total Cooling Capacity (W)', 'Heating Availability Schedule Name',
                'Cooling Availability Schedule Name', 'Dehumidification Control Type', 'Cooling Sensible Heat Ratio', 'Dehumidification Setpoint (percent)', 'Humidification Control Type',
                'Humidification Setpoint (percent)', 'Outdoor Air Method', 'Outdoor Air Flow Rate per Person (m3/s)', 'Outdoor Air Flow Rate per Zone Floor (m3/s-m2)', 'Outdoor Air Flow Rate per Zone (m3/s)',
                'Design Specification Outdoor Air Object', 'Demand Controlled Ventilation Type', 'Outdoor Air Economizer Type', 'Heat Recovery Type', 'Sensible Heat Recovery Effectiveness',
                'Latent Heat Recovery Effectiveness')
        paramvs = (zn, '', zn + '_hvacsched', self.envi_hvacht, self.envi_hvacct, 0.015, 0.009, self['limittype'][self.envi_hvachlt], self.envi_hvachaf if self.envi_hvachlt in ('0', '2') else '',
                   self.envi_hvacshc if self.envi_hvachlt in ('1', '2') else '', self['limittype'][self.envi_hvacclt], self.envi_hvaccaf if self.envi_hvacclt in ('0', '2') else '',
                    self.envi_hvacscc if self.envi_hvacclt in ('1', '2') else '', '', '', 'None', '', '', 'None', '', oam[self.envi_hvacoam], '{:.4f}'.format(self.envi_hvacfrp) if self.envi_hvacoam in ('2', '4', '5') else '',
                    '{:.4f}'.format(self.envi_hvacfrzfa) if self.envi_hvacoam in ('3', '4', '5') else '', '{:.4f}'.format(self.envi_hvacfrz) if self.envi_hvacoam in ('1', '4', '5') else '', '', 'None', 'NoEconomizer', ('None', 'Sensible')[int(self.envi_hvachr)], self.envi_hvachre, 0.65)
        bpy.context.scene['enparams']['hvactemplate'] = 1
        return epentry('HVACTemplate:Zone:IdealLoadsAirSystem', params, paramvs)

    def epewrite(self, zn):
        params = ('Zone Name', 'Zone Conditioning Equipment List Name', 'Zone Air Inlet Node or NodeList Name', 'Zone Air Exhaust Node or NodeList Name',
                  'Zone Air Node Name', 'Zone Return Air Node Name')
        paramvs = (zn, zn + '_Equipment', zn + '_supairnode', '', zn + '_airnode', zn + '_retairnode')
        params2 = ('Name', 'Zone Equipment 1 Object Type', 'Zone Equipment 1 Name', 'Zone Equipment 1 Cooling Sequence', 'Zone Equipment 1 Heating or No-Load Sequence')
        paramvs2 = (zn + '_Equipment', 'ZoneHVAC:IdealLoadsAirSystem', zn + '_Air', 1, 1)
        return epentry('ZoneHVAC:EquipmentConnections', params, paramvs) + epentry('ZoneHVAC:EquipmentList', params2, paramvs2)

    def schedwrite(self, zn):
        pass

class EnViZone(bpy.types.Node, EnViNodes):
    '''Node describing a simulation zone'''
    bl_idname = 'EnViZone'
    bl_label = 'Zone'
    bl_icon = 'SOUND'

    def zupdate(self, context):
        obj = bpy.data.objects[self.zone]
        odm = obj.data.materials
        self.zonevolume = objvol('', obj)
        bfacelist = sorted([face for face in obj.data.polygons if odm[face.material_index].envi_boundary == 1], key=lambda face: -face.center[2])
        buvals = [retuval(odm[face.material_index]) for face in bfacelist]
        bsocklist = ['{}_{}_b'.format(odm[face.material_index].name, face.index) for face in bfacelist]
        sfacelist = sorted([face for face in obj.data.polygons if odm[face.material_index].envi_afsurface == 1 and odm[face.material_index].envi_con_type not in ('Window', 'Door')], key=lambda face: -face.center[2])
        ssocklist = ['{}_{}_s'.format(odm[face.material_index].name, face.index) for face in sfacelist]
        ssfacelist = sorted([face for face in obj.data.polygons if odm[face.material_index].envi_afsurface == 1 and odm[face.material_index].envi_con_type in ('Window', 'Door')], key=lambda face: -face.center[2])
        sssocklist = ['{}_{}_ss'.format(odm[face.material_index].name, face.index) for face in ssfacelist]

        [self.outputs.remove(oname) for oname in self.outputs if oname.bl_idname in ('EnViBoundSocket', 'EnViSFlowSocket', 'EnViSSFlowSocket')]
        [self.inputs.remove(iname) for iname in self.inputs if iname.bl_idname in ('EnViBoundSocket', 'EnViSFlowSocket', 'EnViSSFlowSocket')]

        for sock in bsocklist:
            self.outputs.new('EnViBoundSocket', sock).sn = sock.split('_')[-2]
            self.inputs.new('EnViBoundSocket', sock).sn = sock.split('_')[-2]
        for sock in ssocklist:
            self.outputs.new('EnViSFlowSocket', sock).sn = sock.split('_')[-2]
            self.inputs.new('EnViSFlowSocket', sock).sn = sock.split('_')[-2]
        for sock in sssocklist:
            self.outputs.new('EnViSSFlowSocket', sock).sn = sock.split('_')[-2]
            self.inputs.new('EnViSSFlowSocket', sock).sn = sock.split('_')[-2]                
        for s, sock in enumerate(bsocklist):
            self.outputs[sock].uvalue = '{:.4f}'.format(buvals[s])    
            self.inputs[sock].uvalue = '{:.4f}'.format(buvals[s]) 
            
    def tspsupdate(self, context):
        if self.control != 'Temperature' and self.inputs['TSPSchedule'].links:
            remlink(self, self.inputs['TSPSchedule'].links)
        self.inputs['TSPSchedule'].hide = False if self.control == 'Temperature' else True
        self.update()
                
    zone = bpy.props.StringProperty(name = '', update = zupdate)
    controltype = [("NoVent", "None", "No ventilation control"), ("Constant", "Constant", "From vent availability schedule"), ("Temperature", "Temperature", "Temperature control")]
    control = bpy.props.EnumProperty(name="", description="Ventilation control type", items=controltype, default='NoVent', update=tspsupdate)
    zonevolume = bpy.props.FloatProperty(name = '')
    mvof = bpy.props.FloatProperty(default = 0, name = "", min = 0, max = 1)
    lowerlim = bpy.props.FloatProperty(default = 0, name = "", min = 0, max = 100)
    upperlim = bpy.props.FloatProperty(default = 50, name = "", min = 0, max = 100)

    def init(self, context):
        self['nodeid'] = nodeid(self)
        self['tsps'] = 1
        self.inputs.new('EnViHvacSocket', 'HVAC')
        self.inputs.new('EnViOccSocket', 'Occupancy')
        self.inputs.new('EnViEqSocket', 'Equipment')
        self.inputs.new('EnViInfSocket', 'Infiltration')
        self.inputs.new('EnViSchedSocket', 'TSPSchedule')
        self.inputs.new('EnViSchedSocket', 'VASchedule')

    def update(self):
        sflowdict = {'EnViSFlowSocket': 'Envi surface flow', 'EnViSSFlowSocket': 'Envi sub-surface flow'}
        [bi, si, ssi, bo, so , sso] = [1, 1, 1, 1, 1, 1]
                
        try:
            for inp in [inp for inp in self.inputs if inp.bl_idname in ('EnViBoundSocket', 'EnViSFlowSocket', 'EnViSSFlowSocket')]:
                self.outputs[inp.name].hide = True if inp.links and self.outputs[inp.name].bl_idname == inp.bl_idname else False
    
            for outp in [outp for outp in self.outputs if outp.bl_idname in ('EnViBoundSocket', 'EnViSFlowSocket', 'EnViSSFlowSocket')]:
                self.inputs[outp.name].hide = True if outp.links and self.inputs[outp.name].bl_idname == outp.bl_idname else False
    
            for inp in [inp for inp in self.inputs if inp.bl_idname in ('EnViBoundSocket', 'EnViSFlowSocket', 'EnViSSFlowSocket')]:
                if inp.bl_idname == 'EnViBoundSocket' and not inp.hide and not inp.links:
                    bi = 0
                elif inp.bl_idname in sflowdict:
                    if (not inp.hide and not inp.links) or (inp.links and inp.links[0].from_node.bl_label != sflowdict[inp.bl_idname]):
                        si = 0
                        if inp.links:
                            remlink(self, [inp.links[0]])    
            
            for outp in [outp for outp in self.outputs if outp.bl_idname in ('EnViBoundSocket', 'EnViSFlowSocket', 'EnViSSFlowSocket')]:
                if outp.bl_idname == 'EnViBoundSocket' and not outp.hide and not outp.links:
                    bo = 0
                elif outp.bl_idname  in sflowdict:
                    if (not outp.hide and not outp.links) or (outp.links and outp.links[0].to_node.bl_label != sflowdict[outp.bl_idname]):
                        so = 0
                        if outp.links:
                            remlink(self, [outp.links[0]])

            
                    
        except Exception as e:
            print("Don't panic")
        nodecolour(self, (self.control == 'Temperature' and not self.inputs['TSPSchedule'].is_linked) or not all((bi, si, ssi, bo, so, sso)))
    
    def uvsockupdate(self):
        for sock in self.outputs:
            socklink(sock, self['nodeid'].split('@')[1])
            if sock.bl_idname == 'EnViBoundSocket':
                uvsocklink(sock, self['nodeid'].split('@')[1])
                
    def draw_buttons(self, context, layout):
        newrow(layout, 'Zone:', self, 'zone')
        yesno = (1, 1, self.control == 'Temperature', self.control == 'Temperature', self.control == 'Temperature')
        vals = (("Volume:", "zonevolume"), ("Control type:", "control"), ("Minimum OF:", "mvof"), ("Lower:", "lowerlim"), ("Upper:", "upperlim"))
        [newrow(layout, val[0], self, val[1]) for v, val in enumerate(vals) if yesno[v]]

    def epwrite(self):
        (tempschedname, mvof, lowerlim, upperlim) = (self.zone + '_tspsched', self.mvof, self.lowerlim, self.upperlim) if self.inputs['TSPSchedule'].is_linked else ('', '', '', '')
        vaschedname = self.zone + '_vasched' if self.inputs['VASchedule'].is_linked else ''
        params = ('Zone Name',
        'Ventilation Control Mode', 'Ventilation Control Zone Temperature Setpoint Schedule Name',
        'Minimum Venting Open Factor (dimensionless)',
        'Indoor and Outdoor Temperature Diffeence Lower Limit for Maximum Venting Opening Factor (deltaC)',
        'Indoor and Outdoor Temperature Diffeence Upper Limit for Minimum Venting Opening Factor (deltaC)',
        'Indoor and Outdoor Enthalpy Difference Lower Limit For Maximum Venting Open Factor (deltaJ/kg)',
        'Indoor and Outdoor Enthalpy Difference Upper Limit for Minimun Venting Open Factor (deltaJ/kg)',
        'Venting Availability Schedule Name')

        paramvs = (self.zone, self.control, tempschedname, mvof, lowerlim, upperlim, '0.0', '300000.0', vaschedname)
        return epentry('AirflowNetwork:MultiZone:Zone', params, paramvs)

class EnViTC(bpy.types.Node, EnViNodes):
    '''Zone Thermal Chimney node'''
    bl_idname = 'EnViTC'
    bl_label = 'Chimney'
    bl_icon = 'SOUND'

    def zupdate(self, context):
        zonenames= []
        obj = bpy.data.objects[self.zone]
        odm = obj.data.materials
        bsocklist = ['{}_{}_b'.format(odm[face.material_index].name, face.index)  for face in obj.data.polygons if odm[face.material_index].envi_boundary == 1 and odm[face.material_index].name not in [outp.name for outp in self.outputs if outp.bl_idname == 'EnViBoundSocket']]

        for oname in [outputs for outputs in self.outputs if outputs.name not in bsocklist and outputs.bl_idname == 'EnViBoundSocket']:
            self.outputs.remove(oname)
        for iname in [inputs for inputs in self.inputs if inputs.name not in bsocklist and inputs.bl_idname == 'EnViBoundSocket']:
            self.inputs.remove(iname)
        for sock in sorted(set(bsocklist)):
            if not self.outputs.get(sock):
                self.outputs.new('EnViBoundSocket', sock).sn = sock.split('_')[-2]
            if not self.inputs.get(sock):
                self.inputs.new('EnViBoundSocket', sock).sn = sock.split('_')[-2]
        for sock in (self.inputs[:] + self.outputs[:]):
            if sock.bl_idname == 'EnViBoundSocket' and sock.links:
                zonenames += [(link.from_node.zone, link.to_node.zone)[sock.is_output] for link in sock.links]

        nodecolour(self, all([mat.envi_con_type != 'Window' for mat in bpy.data.objects[self.zone].data.materials if mat]))
        self['zonenames'] = zonenames

    def supdate(self, context):
        self.inputs.new['Schedule'].hide = False if self.sched == 'Sched' else True

    zone = bpy.props.StringProperty(name = '', default = "en_Chimney")
    sched = bpy.props.EnumProperty(name="", description="Ventilation control type", items=[('On', 'On', 'Always on'), ('Off', 'Off', 'Always off'), ('Sched', 'Schedule', 'Scheduled operation')], default='On', update = supdate)
    waw = bpy.props.FloatProperty(name = '', min = 0.001, default = 1)
    ocs = bpy.props.FloatProperty(name = '', min = 0.001, default = 1)
    odc = bpy.props.FloatProperty(name = '', min = 0.001, default = 0.6)

    def init(self, context):
        self['nodeid'] = nodeid(self)
        self.inputs.new('EnViSchedSocket', 'Schedule')
        self['zonenames'] = []

    def draw_buttons(self, context, layout):
        newrow(layout, 'Zone:', self, 'zone')
        newrow(layout, 'Schedule:', self, 'sched')
        newrow(layout, 'Width Absorber:', self, 'waw')
        newrow(layout, 'Outlet area:', self, 'ocs')
        newrow(layout, 'Outlet DC:', self, 'odc')

        for z, zn in enumerate(self['zonenames']):
            row=layout.row()
            row.label(zn)
            row=layout.row()
            row.prop(self, '["Distance {}"]'.format(z))
            row=layout.row()
            row.prop(self, '["Relative Ratio {}"]'.format(z))
            row=layout.row()
            row.prop(self, '["Cross Section {}"]'.format(z))

    def update(self):
        bi, bo = 1, 1
        zonenames, fheights, fareas = [], [], []
        for inp in [inp for inp in self.inputs if inp.bl_idname == 'EnViBoundSocket']:
            self.outputs[inp.name].hide = True if inp.is_linked and self.outputs[inp.name].bl_idname == inp.bl_idname else False

        for outp in [outp for outp in self.outputs if outp.bl_idname in 'EnViBoundSocket']:
            self.inputs[outp.name].hide = True if outp.is_linked and self.inputs[outp.name].bl_idname == outp.bl_idname else False

        if [inp for inp in self.inputs if inp.bl_idname == 'EnViBoundSocket' and not inp.hide and not inp.links]:
            bi = 0
                
        if [outp for outp in self.outputs if outp.bl_idname == 'EnViBoundSocket' and not outp.hide and not outp.links]:
            bo = 0
        
        nodecolour(self, not all((bi, bo)))
        
        for sock in [sock for sock in self.inputs[:] + self.outputs[:] if sock.bl_idname == 'EnViBoundSocket']:
            if sock.links and self.zone in [o.name for o in bpy.data.objects]:
                zonenames += [link.to_node.zone for link in sock.links]
                fheights += [max([(bpy.data.objects[self.zone].matrix_world * vert.co)[2] for vert in bpy.data.objects[self.zone].data.vertices]) - (bpy.data.objects[link.to_node.zone].matrix_world * bpy.data.objects[link.to_node.zone].data.polygons[int(link.to_socket.sn)].center)[2] for link in sock.links]
                fareas += [facearea(bpy.data.objects[link.to_node.zone], bpy.data.objects[link.to_node.zone].data.polygons[int(link.to_socket.sn)]) for link in sock.links]
    
            self['zonenames'] = zonenames
            for z, zn in enumerate(self['zonenames']):
                self['Distance {}'.format(z)] = fheights[z]
                self['Relative Ratio {}'.format(z)] = 1.0
                self['Cross Section {}'.format(z)] = fareas[z]
        for sock in self.outputs:
            socklink(sock, self['nodeid'].split('@')[1])

    def epwrite(self):
        scheduled = 1 if self.inputs['Schedule'].links and not self.inputs['Schedule'].links[0].to_node.use_custom_color else 0
        paramvs = ('{}_TC'.format(self.zone), self.zone, ('', '{}_TCSched'.format(self.zone))[scheduled], self.waw, self.ocs, self.odc)
        params = ('Name of Thermal Chimney System', 'Name of Thermal Chimney Zone', 'Availability Schedule Name', 'Width of the Absorber Wall',
                  'Cross Sectional Area of Air Channel Outlet', 'Discharge Coefficient')

        for z, zn in enumerate(self['zonenames']):
            params += (' Zone Name {}'.format(z + 1), 'Distance from the Top of the Thermal Chimney to Inlet {}'.format(z + 1), 'Relative Ratios of Air Flow Rates Passing through Zone {}'.format(z + 1),
                       'Cross Sectional Areas of Air Channel Inlet {}'.format(z + 1))
            paramvs += (zn, self['Distance {}'.format(z)], self['Relative Ratio {}'.format(z)], self['Cross Section {}'.format(z)])

        return epentry('ZoneThermalChimney', params, paramvs)

class EnViSSFlowNode(bpy.types.Node, EnViNodes):
    '''Node describing a sub-surface airflow component'''
    bl_idname = 'EnViSSFlow'
    bl_label = 'Envi sub-surface flow'
    bl_icon = 'SOUND'

    def supdate(self, context):
        if self.linkmenu in ('Crack', 'EF', 'ELA') or self.controls != 'Temperature':
            if self.inputs['TSPSchedule'].is_linked:
                remlink(self, self.inputs['TSPSchedule'].links)
        if self.linkmenu in ('Crack', 'EF', 'ELA') or self.controls in ('ZoneLevel', 'NoVent'):
            if self.inputs['VASchedule'].is_linked:
                remlink(self, self.inputs['VASchedule'].links)

        self.inputs['TSPSchedule'].hide = False if self.linkmenu in ('SO', 'DO', 'HO') and self.controls == 'Temperature' else True
        self.inputs['VASchedule'].hide = False if self.linkmenu in ('SO', 'DO', 'HO') else True
        self.legal()

    linktype = [("SO", "Simple Opening", "Simple opening element"),("DO", "Detailed Opening", "Detailed opening element"),
        ("HO", "Horizontal Opening", "Horizontal opening element"),("Crack", "Crack", "Crack aperture used for leakage calculation"),
        ("ELA", "ELA", "Effective leakage area")]

    linkmenu = bpy.props.EnumProperty(name="Type", description="Linkage type", items=linktype, default='SO', update = supdate)

    wdof1 = bpy.props.FloatProperty(default = 0.1, min = 0.001, max = 1, name = "", description = 'Opening Factor 1 (dimensionless)')
    controltype = [("ZoneLevel", "ZoneLevel", "Zone level ventilation control"), ("NoVent", "None", "No ventilation control"),
                   ("Constant", "Constant", "From vent availability schedule"), ("Temperature", "Temperature", "Temperature control")]
    controls = bpy.props.EnumProperty(name="", description="Ventilation control type", items=controltype, default='ZoneLevel', update = supdate)
    mvof = bpy.props.FloatProperty(default = 0, min = 0, max = 1, name = "", description = 'Minimium venting open factor')
    lvof = bpy.props.FloatProperty(default = 0, min = 0, max = 100, name = "", description = 'Indoor and Outdoor Temperature Difference Lower Limit For Maximum Venting Open Factor (deltaC)')
    uvof = bpy.props.FloatProperty(default = 1, min = 1, max = 100, name = "", description = 'Indoor and Outdoor Temperature Difference Upper Limit For Minimum Venting Open Factor (deltaC)')
    amfcc = bpy.props.FloatProperty(default = 0.001, min = 0.00001, max = 1, name = "", description = 'Air Mass Flow Coefficient When Opening is Closed (kg/s-m)')
    amfec = bpy.props.FloatProperty(default = 0.65, min = 0.5, max = 1, name = '', description =  'Air Mass Flow Exponent When Opening is Closed (dimensionless)')
    lvo = bpy.props.EnumProperty(items = [('NonPivoted', 'NonPivoted', 'Non pivoting opening'), ('HorizontallyPivoted', 'HPivoted', 'Horizontally pivoting opening')], name = '', default = 'NonPivoted', description = 'Type of Rectanguler Large Vertical Opening (LVO)')
    ecl = bpy.props.FloatProperty(default = 0.0, min = 0, name = '', description = 'Extra Crack Length or Height of Pivoting Axis (m)')
    noof = bpy.props.IntProperty(default = 2, min = 2, max = 4, name = '', description = 'Number of Sets of Opening Factor Data')
    spa = bpy.props.IntProperty(default = 90, min = 0, max = 90, name = '', description = 'Sloping Plane Angle')
    dcof = bpy.props.FloatProperty(default = 1, min = 0.01, max = 1, name = '', description = 'Discharge Coefficient')
    ddtw = bpy.props.FloatProperty(default = 0.0001, min = 0, max = 10, name = '', description = 'Minimum Density Difference for Two-way Flow')
    amfc = bpy.props.FloatProperty(min = 0.001, max = 1, default = 0.01, name = "")
    amfe = bpy.props.FloatProperty(min = 0.5, max = 1, default = 0.65, name = "")
    dlen = bpy.props.FloatProperty(default = 2, name = "")
    dhyd = bpy.props.FloatProperty(default = 0.1, name = "")
    dcs = bpy.props.FloatProperty(default = 0.1, name = "")
    dsr = bpy.props.FloatProperty(default = 0.0009, name = "")
    dlc = bpy.props.FloatProperty(default = 1.0, name = "")
    dhtc = bpy.props.FloatProperty(default = 0.772, name = "")
    dmtc = bpy.props.FloatProperty(default = 0.0001, name = "")
    fe = bpy.props.FloatProperty(default = 0.6, min = 0, max = 1, name = "")
    rpd = bpy.props.FloatProperty(default = 4, min = 0.1, max = 50, name = "")
    of1 = bpy.props.FloatProperty(default = 0.0, min = 0.0, max = 0, name = '', description = 'Opening Factor {} (dimensionless)')
    (of2, of3, of4) =  [bpy.props.FloatProperty(default = 1.0, min = 0.01, max = 1, name = '', description = 'Opening Factor {} (dimensionless)'.format(i)) for i in range(3)]
    (dcof1, dcof2, dcof3, dcof4) = [bpy.props.FloatProperty(default = 0.0, min = 0.01, max = 1, name = '', description = 'Discharge Coefficient for Opening Factor {} (dimensionless)'.format(i)) for i in range(4)]
    (wfof1, wfof2, wfof3, wfof4) = [bpy.props.FloatProperty(default = 0.0, min = 0, max = 1, name = '', description = 'Width Factor for Opening Factor {} (dimensionless)'.format(i)) for i in range(4)]
    (hfof1, hfof2, hfof3, hfof4) = [bpy.props.FloatProperty(default = 0.0, min = 0, max = 1, name = '', description = 'Height Factor for Opening Factor {} (dimensionless)'.format(i)) for i in range(4)]
    (sfof1, sfof2, sfof3, sfof4) = [bpy.props.FloatProperty(default = 0.0, min = 0, max = 1, name = '', description = 'Start Height Factor for Opening Factor {} (dimensionless)'.format(i)) for i in range(4)]
    dcof = bpy.props.FloatProperty(default = 0.2, min = 0.01, max = 1, name = '', description = 'Discharge Coefficient')
    extnode =  bpy.props.BoolProperty(default = 0)
    actlist = [("0", "Opening factor", "Actuate the opening factor")]
    acttype = bpy.props.EnumProperty(name="", description="Actuator type", items=actlist, default='0')
    compdict = {'0': 'AirFlow Network Window/Door Opening'}
    actdict =  {'0': ('Venting Opening Factor', 'of')}
    adict = {'Window': 'win', 'Door': 'door'}

    def init(self, context):
        self['nodeid'] = nodeid(self)
        self['init'] = 1
        self['ela'] = 1.0
        self.inputs.new('EnViSchedSocket', 'VASchedule')
        self.inputs.new('EnViSchedSocket', 'TSPSchedule')
        self.inputs['TSPSchedule'].hide = True
        self.inputs.new('EnViSSFlowSocket', 'Node 1', identifier = 'Node1_s')
        self.inputs.new('EnViSSFlowSocket', 'Node 2', identifier = 'Node2_s')
        self.outputs.new('EnViSSFlowSocket', 'Node 1', identifier = 'Node1_s')
        self.outputs.new('EnViSSFlowSocket', 'Node 2', identifier = 'Node2_s')
        self.color = (1.0, 0.3, 0.3)
        self['layoutdict'] = {'SO':(('Closed FC', 'amfcc'), ('Closed FE', 'amfec'), ('Density diff', 'ddtw'), ('DC', 'dcof')), 'DO':(('Closed FC', 'amfcc'), ('Closed FE', 'amfec'),
                           ('Opening type', 'lvo'), ('Crack length', 'ecl'), ('OF Number', 'noof'), ('OF1', 'of1'), ('DC1', 'dcof1'), ('Width OF1', 'wfof1'), ('Height OF1', 'hfof1'),
                            ('Start height OF1', 'sfof1'), ('OF2', 'of2'), ('DC2', 'dcof2'), ('Width OF2', 'wfof2'), ('Height OF2', 'hfof2'), ('Start height OF2', 'sfof2')),
                            'OF3': (('OF3', 'of3'), ('DC3', 'dcof3'), ('Width OF3', 'wfof3'), ('Height OF3', 'hfof3'), ('Start height OF3', 'sfof3')),
                            'OF4': (('OF4', 'of4'), ('DC4', 'dcof4'), ('Width OF4', 'wfof4'), ('Height OF4', 'hfof4'), ('Start height OF4', 'sfof4')),
                            'HO': (('Closed FC', 'amfcc'), ('Closed FE', 'amfec'), ('Slope', 'spa'), ('DC', 'dcof')), 'Crack': (('Coefficient', 'amfc'), ('Exponent', 'amfe'), ('Factor', 'of1')),
                            'ELA': (('ELA', '["ela"]'), ('DC', 'dcof'), ('PA diff', 'rpd'), ('FE', 'fe'))}

    def update(self):
        if self.get('layoutdict'):
            for sock in self.outputs:
                socklink(sock, self['nodeid'].split('@')[1])
            if self.linkmenu == 'ELA':
                retelaarea(self)
            self.extnode = 0
            for sock in self.inputs[:] + self.outputs[:]:
                for l in sock.links:
                    if (l.from_node, l.to_node)[sock.is_output].bl_idname == 'EnViExt':
                        self.extnode = 1
            if self.outputs.get('Node 2'):
                sockhide(self, ('Node 1', 'Node 2'))
            self.legal()

    def draw_buttons(self, context, layout):
        layout.prop(self, 'linkmenu')
        if self.linkmenu in ('SO', 'DO', 'HO'):
            newrow(layout, 'Win/Door OF:', self, 'wdof1')
            newrow(layout, "Control type:", self, 'controls')
            if self.linkmenu in ('SO', 'DO') and self.controls == 'Temperature':
                newrow(layout, "Limit OF:", self, 'mvof')
                newrow(layout, "Lower OF:", self, 'lvof')
                newrow(layout, "Upper OF:", self, 'uvof')

        row = layout.row()
        row.label('Component options:')

        for vals in self['layoutdict'][self.linkmenu]:
            newrow(layout, vals[0], self, vals[1])
        if self.noof > 2:
            for of3vals in self['layoutdict']['OF3']:
                newrow(layout, of3vals[0], self, of3vals[1])
            if self.noof > 3:
                for of4vals in self['layoutdict']['OF4']:
                    newrow(layout, of4vals[0], self, of4vals[1])

    def epwrite(self, exp_op, enng):
        surfentry, en, snames = '', '', []
        tspsname = '{}_tspsched'.format(self.name) if self.inputs['TSPSchedule'].is_linked and self.linkmenu in ('SO', 'DO', 'HO') and self.controls == 'Temperature' else ''
        vasname = '{}_vasched'.format(self.name) if self.inputs['VASchedule'].is_linked and self.linkmenu in ('SO', 'DO', 'HO') else ''
        for sock in (self.inputs[:] + self.outputs[:]):
            for link in sock.links:
                othernode = (link.from_node, link.to_node)[sock.is_output]
                if othernode.bl_idname == 'EnViExt' and enng['enviparams']['wpca'] == 1:
                    en = othernode.name

        if self.linkmenu == 'DO':
            cfparams = ('Name', 'Air Mass Flow Coefficient When Opening is Closed (kg/s-m)', 'Air Mass Flow Exponent When Opening is Closed (dimensionless)',
                       'Type of Rectanguler Large Vertical Opening (LVO)', 'Extra Crack Length or Height of Pivoting Axis (m)', 'Number of Sets of Opening Factor Data',
                        'Opening Factor 1 (dimensionless)', 'Discharge Coefficient for Opening Factor 1 (dimensionless)', 'Width Factor for Opening Factor 1 (dimensionless)',
                        'Height Factor for Opening Factor 1 (dimensionless)', 'Start Height Factor for Opening Factor 1 (dimensionless)', 'Opening Factor 2 (dimensionless)',
                        'Discharge Coefficient for Opening Factor 2 (dimensionless)', 'Width Factor for Opening Factor 2 (dimensionless)', 'Height Factor for Opening Factor 2 (dimensionless)',
                        'Start Height Factor for Opening Factor 2 (dimensionless)', 'Opening Factor 3 (dimensionless)', 'Discharge Coefficient for Opening Factor 3 (dimensionless)',
                        'Width Factor for Opening Factor 3 (dimensionless)', 'Height Factor for Opening Factor 3 (dimensionless)', 'Start Height Factor for Opening Factor 3 (dimensionless)',
                        'Opening Factor 4 (dimensionless)', 'Discharge Coefficient for Opening Factor 4 (dimensionless)', 'Width Factor for Opening Factor 4 (dimensionless)',
                        'Height Factor for Opening Factor 4 (dimensionless)', 'Start Height Factor for Opening Factor 4 (dimensionless)')
            cfparamsv = ('{}_{}'.format(self.name, self.linkmenu), self.amfcc, self.amfec, self.lvo, self.ecl, self.noof, '{:3f}'.format(self.of1), self.dcof1,self.wfof1, self.hfof1, self.sfof1,
                         self.of2, self.dcof2,self.wfof2, self.hfof2, self.sfof2, self.of3, self.dcof3,self.wfof3, self.hfof3, self.sfof3, self.of4, self.dcof4,self.wfof4, self.hfof4, self.sfof4)

        elif self.linkmenu == 'SO':
            cfparams = ('Name', 'Air Mass Flow Coefficient When Opening is Closed (kg/s-m)', 'Air Mass Flow Exponent When Opening is Closed (dimensionless)', 'Minimum Density Difference for Two-Way Flow (kg/m3)', 'Discharge Coefficient (dimensionless)')
            cfparamsv = ('{}_{}'.format(self.name, self.linkmenu), self.amfcc, self.amfec, self.ddtw, self.dcof)

        elif self.linkmenu == 'HO':
            if not (self.inputs['Node 1'].is_linked or self.inputs['Node 2'].is_linked and self.outputs['Node 1'].is_linked or self.outputs['Node 2'].is_linked):
                exp_op.report({'ERROR'}, 'All horizonal opening surfaces must sit on the boundary between two thermal zones')

            cfparams = ('Name', 'Air Mass Flow Coefficient When Opening is Closed (kg/s-m)', 'Air Mass Flow Exponent When Opening is Closed (dimensionless)', 'Sloping Plane Angle (deg)', 'Discharge Coefficient (dimensionless)')
            cfparamsv = ('{}_{}'.format(self.name, self.linkmenu), self.amfcc, self.amfec, self.spa, self.dcof)

        elif self.linkmenu == 'ELA':
            cfparams = ('Name', 'Effective Leakage Area (m2)', 'Discharge Coefficient (dimensionless)', 'Reference Pressure Difference (Pa)', 'Air Mass Flow Exponent (dimensionless)')
            cfparamsv = ('{}_{}'.format(self.name, self.linkmenu), '{:5f}'.format(self['ela']), '{:2f}'.format(self.dcof), '{:1f}'.format(self.rpd), '{:3f}'.format(self.amfe))

        elif self.linkmenu == 'Crack':
            crname = 'ReferenceCrackConditions' if enng['enviparams']['crref'] == 1 else ''
            cfparams = ('Name', 'Air Mass Flow Coefficient at Reference Conditions (kg/s)', 'Air Mass Flow Exponent (dimensionless)', 'Reference Crack Conditions')
            cfparamsv = ('{}_{}'.format(self.name, self.linkmenu), self.amfc, self.amfe, crname)

        cftypedict = {'DO':'Component:DetailedOpening', 'SO':'Component:SimpleOpening', 'HO':'Component:HorizontalOpening', 'Crack':'Surface:Crack', 'ELA':'Surface:EffectiveLeakageArea'}
        cfentry = epentry('AirflowNetwork:MultiZone:{}'.format(cftypedict[self.linkmenu]), cfparams, cfparamsv)

        for sock in (self.inputs[:] + self.outputs[:]):
            for link in sock.links:
                othersock = (link.from_socket, link.to_socket)[sock.is_output]
                othernode = (link.from_node, link.to_node)[sock.is_output]

                if sock.bl_idname == 'EnViSSFlowSocket' and othernode.bl_idname == 'EnViZone':
                    zn = othernode.zone
                    sn = othersock.sn
                    snames.append(('win-', 'door-')[bpy.data.materials[othersock.name[:-len(sn)-4]].envi_con_type == 'Door']+zn+'_'+sn)
                    params = ('Surface Name', 'Leakage Component Name', 'External Node Name', 'Window/Door Opening Factor')
                    paramvs = (snames[-1], '{}_{}'.format(self.name, self.linkmenu), en, self.wdof1)
                    if self.linkmenu in ('SO', 'DO'):
                        params += ('Ventilation Control Mode', 'Vent Temperature Schedule Name', 'Limit  Value on Multiplier for Modulating Venting Open Factor (dimensionless)', \
                        'Lower Value on Inside/Outside Temperature Difference for Modulating the Venting Open Factor (deltaC)', 'Upper Value on Inside/Outside Temperature Difference for Modulating the Venting Open Factor (deltaC)',\
                        'Lower Value on Inside/Outside Enthalpy Difference for Modulating the Venting Open Factor (J/kg)', 'Upper Value on Inside/Outside Enthalpy Difference for Modulating the Venting Open Factor (J/kg)', 'Venting Availability Schedule Name')
                        paramvs += (self.controls if self.linkmenu in ('SO', 'DO', 'HO') else '', tspsname, '{:.2f}'.format(self.mvof), self.lvof, self.uvof, '', '', vasname)
                    surfentry += epentry('AirflowNetwork:MultiZone:Surface', params, paramvs)
        self['sname'] = snames
        self.legal()
        return surfentry + cfentry

    def legal(self):
        nodecolour(self, 1) if (self.controls == 'Temperature' and not self.inputs['TSPSchedule'].is_linked) or (bpy.data.node_groups[self['nodeid'].split('@')[1]]['enviparams']['wpca'] and not self.extnode) else nodecolour(self, 0)
        for sock in self.inputs[:] + self.outputs[:]:
            sock.hide = sock.hide
        bpy.data.node_groups[self['nodeid'].split('@')[1]].interface_update(bpy.context)

class EnViSFlowNode(bpy.types.Node, EnViNodes):
    '''Node describing a surface airflow component'''
    bl_idname = 'EnViSFlow'
    bl_label = 'Envi surface flow'
    bl_icon = 'SOUND'

    linktype = [("Crack", "Crack", "Crack aperture used for leakage calculation"),
        ("ELA", "ELA", "Effective leakage area")]

    linkmenu = bpy.props.EnumProperty(name="Type", description="Linkage type", items=linktype, default='ELA')
    of = bpy.props.FloatProperty(default = 0.1, min = 0.001, max = 1, name = "", description = 'Opening Factor 1 (dimensionless)')
    ecl = bpy.props.FloatProperty(default = 0.0, min = 0, name = '', description = 'Extra Crack Length or Height of Pivoting Axis (m)')
    dcof = bpy.props.FloatProperty(default = 1, min = 0, max = 1, name = '', description = 'Discharge Coefficient')
    amfc = bpy.props.FloatProperty(min = 0.001, max = 1, default = 0.01, name = "")
    amfe = bpy.props.FloatProperty(min = 0.5, max = 1, default = 0.65, name = "")
    dlen = bpy.props.FloatProperty(default = 2, name = "")
    dhyd = bpy.props.FloatProperty(default = 0.1, name = "")
    dcs = bpy.props.FloatProperty(default = 0.1, name = "")
    dsr = bpy.props.FloatProperty(default = 0.0009, name = "")
    dlc = bpy.props.FloatProperty(default = 1.0, name = "")
    dhtc = bpy.props.FloatProperty(default = 0.772, name = "")
    dmtc = bpy.props.FloatProperty(default = 0.0001, name = "")
    cf = bpy.props.FloatProperty(default = 1, min = 0, max = 1, name = "")
    rpd = bpy.props.FloatProperty(default = 4, min = 0.1, max = 50, name = "")
    fe = bpy.props.FloatProperty(default = 4, min = 0.1, max = 1, name = "", description = 'Fan Efficiency')
    pr = bpy.props.IntProperty(default = 500, min = 1, max = 10000, name = "", description = 'Fan Pressure Rise')
    mf = bpy.props.FloatProperty(default = 0.1, min = 0.001, max = 5, name = "", description = 'Maximum Fan Flow Rate (m3/s)')
    extnode =  bpy.props.BoolProperty(default = 0)

    def init(self, context):
        self['nodeid'] = nodeid(self)
        self['ela'] = 1.0
        self.inputs.new('EnViSFlowSocket', 'Node 1')
        self.inputs.new('EnViSFlowSocket', 'Node 2')
        self.outputs.new('EnViSFlowSocket', 'Node 1')
        self.outputs.new('EnViSFlowSocket', 'Node 2')

    def update(self):
        for sock in self.outputs:
            socklink(sock, self['nodeid'].split('@')[1])
        if self.linkmenu == 'ELA':
            retelaarea(self)
        self.extnode = 0
        for sock in self.inputs[:] + self.outputs[:]:
            for l in sock.links:
                if (l.from_node, l.to_node)[sock.is_output].bl_idname == 'EnViExt':
                    self.extnode = 1
        if self.outputs.get('Node 2'):
            sockhide(self, ('Node 1', 'Node 2'))
        self.legal()

    def draw_buttons(self, context, layout):
        layout.prop(self, 'linkmenu')
        layoutdict = {'Crack':(('Coefficient', 'amfc'), ('Exponent', 'amfe'), ('Factor', 'of')), 'ELA':(('ELA (m^2)', '["ela"]'), ('DC', 'dcof'), ('PA diff (Pa)', 'rpd'), ('FE', 'amfe')),
        'EF':(('Off FC', 'amfc'), ('Off FE', 'amfe'), ('Efficiency', 'fe'), ('PA rise (Pa)', 'pr'), ('Max flow', 'mf'))}
        for vals in layoutdict[self.linkmenu]:
            newrow(layout, '{}:'.format(vals[0]), self, vals[1])

    def epwrite(self, exp_op, enng):
        fentry, crentry, zn, en, surfentry, crname, snames = '', '', '', '', '', '', []
        for sock in (self.inputs[:] + self.outputs[:]):
            for link in sock.links:
                othernode = (link.from_node, link.to_node)[sock.is_output]
                if othernode.bl_idname == 'EnViExt' and enng['enviparams']['wpca'] == 1:
                    en = othernode.name

        if self.linkmenu == 'ELA':
            cfparams = ('Name', 'Effective Leakage Area (m2)', 'Discharge Coefficient (dimensionless)', 'Reference Pressure Difference (Pa)', 'Air Mass Flow Exponent (dimensionless)')
            cfparamvs = ('{}_{}'.format(self.name, self.linkmenu), '{:.5f}'.format(self['ela']), self.dcof, self.rpd, '{:.5f}'.format(self.amfe))

        elif self.linkmenu == 'Crack':
            crname = 'ReferenceCrackConditions' if enng['enviparams']['crref'] == 1 else ''
            cfparams = ('Name', 'Air Mass Flow Coefficient at Reference Conditions (kg/s)', 'Air Mass Flow Exponent (dimensionless)', 'Reference Crack Conditions')
            cfparamvs = ('{}_{}'.format(self.name, self.linkmenu), '{:.5f}'.format(self.amfc), '{:.5f}'.format(self.amfe), crname)

        elif self.linkmenu == 'EF':
            cfparams = ('Name', 'Air Mass Flow Coefficient When the Zone Exhaust Fan is Off at Reference Conditions (kg/s)', 'Air Mass Flow Exponent When the Zone Exhaust Fan is Off (dimensionless)')
            cfparamvs = ('{}_{}'.format(self.name, self.linkmenu), self.amfc, self.amfe)
            schedname = self.inputs['Fan Schedule'].links[0].from_node.name if self.inputs['Fan Schedule'].is_linked else ''
            for sock in [inp for inp in self.inputs if 'Node' in inp.name and inp.is_linked] + [outp for outp in self.outputs if 'Node' in outp.name and outp.is_linked]:
                zname = (sock.links[0].from_node, sock.links[0].to_node)[sock.is_output].zone
            fparams = ('Name', 'Availability Schedule Name', 'Fan Efficiency', 'Pressure Rise (Pa)', 'Maximum Flow Rate (m3/s)', 'Air Inlet Node Name', 'Air Outlet Node Name', 'End-Use Subcategory')
            fparamvs = ('{}_{}'.format(self.name,  self.linkmenu), schedname, self.fe, self.pr, self.mf, '{} Exhaust Node'.format(zname), '{} Exhaust Fan Outlet Node'.format(zname), '{} Exhaust'.format(zname))
            fentry = epentry('Fan:ZoneExhaust', fparams, fparamvs)

        cftypedict = {'Crack':'Surface:Crack', 'ELA':'Surface:EffectiveLeakageArea', 'EF': 'Component:ZoneExhaustFan'}
        cfentry = epentry('AirflowNetwork:MultiZone:{}'.format(cftypedict[self.linkmenu]), cfparams, cfparamvs)

        for sock in self.inputs[:] + self.outputs[:]:
            for link in sock.links:
                othersock = (link.from_socket, link.to_socket)[sock.is_output]
                othernode = (link.from_node, link.to_node)[sock.is_output]
                if sock.bl_idname == 'EnViSFlowSocket' and othernode.bl_idname == 'EnViZone':
                    sn = othersock.sn
                    zn = othernode.zone
                    snames.append(zn+'_'+sn)
                    params = ('Surface Name', 'Leakage Component Name', 'External Node Name', 'Window/Door Opening Factor, or Crack Factor (dimensionless)')
                    paramvs = (snames[-1], '{}_{}'.format(self.name, self.linkmenu), en, '{:.5f}'.format(self.of))
                    surfentry += epentry('AirflowNetwork:MultiZone:Surface', params, paramvs)

        self['sname'] = snames
        self.legal()
        return surfentry + cfentry + crentry + fentry

    def legal(self):
        try:
            nodecolour(self, 1) if not self.extnode and bpy.data.node_groups[self['nodeid'].split('@')[1]]['enviparams']['wpca'] else nodecolour(self, 0)
            bpy.data.node_groups[self['nodeid'].split('@')[1]].interface_update(bpy.context)
        except:
            nodecolour(self, 1)

class EnViExtNode(bpy.types.Node, EnViNodes):
    '''Node describing an EnVi external node'''
    bl_idname = 'EnViExt'
    bl_label = 'Envi External Node'
    bl_icon = 'SOUND'

    height = bpy.props.FloatProperty(default = 1.0)
    (wpc1, wpc2, wpc3, wpc4, wpc5, wpc6, wpc7, wpc8, wpc9, wpc10, wpc11, wpc12) = [bpy.props.FloatProperty(name = '', default = 0, min = -1, max = 1) for x in range(12)]
    enname = bpy.props.StringProperty()

    def init(self, context):
        self['nodeid'] = nodeid(self)
        self.inputs.new('EnViSSFlowSocket', 'Sub surface')
        self.inputs.new('EnViSFlowSocket', 'Surface')
        self.outputs.new('EnViSSFlowSocket', 'Sub surface')
        self.outputs.new('EnViSFlowSocket', 'Surface')

    def draw_buttons(self, context, layout):
        layout.prop(self, 'height')
        row= layout.row()
        row.label('WPC Values')
        for w in range(1, 13):
            row = layout.row()
            row.prop(self, 'wpc{}'.format(w))

    def update(self):
        for sock in self.outputs:
            socklink(sock, self['nodeid'].split('@')[1])
        sockhide(self, ('Sub surface', 'Surface'))

    def epwrite(self, enng):
        enentry, wpcname, wpcentry = '', '', ''
        for sock in self.inputs[:] + self.outputs[:]:
            for link in sock.links:
                wpcname = self.name+'_wpcvals'
                wpcs = (self.wpc1, self.wpc2, self.wpc3, self.wpc4, self.wpc5, self.wpc6, self.wpc7, self.wpc8, self.wpc9, self.wpc10, self.wpc11, self.wpc12)
                wparams = ['Name', 'AirflowNetwork:MultiZone:WindPressureCoefficientArray Name'] + ['Wind Pressure Coefficient Value {} (dimensionless)'.format(w + 1) for w in range(enng['enviparams']['wpcn'])]
                wparamvs =  ['{}_wpcvals'.format(self.name), 'WPC Array'] + [wpcs[wp] for wp in range(len(wparams))]
                wpcentry = epentry('AirflowNetwork:MultiZone:WindPressureCoefficientValues', wparams, wparamvs)
                params = ['Name', 'External Node Height (m)', 'Wind Pressure Coefficient Values Object Name']
                paramvs = [self.name, self.height, wpcname]
                enentry = epentry('AirflowNetwork:MultiZone:ExternalNode', params, paramvs)
        return enentry + wpcentry

class EnViSched(bpy.types.Node, EnViNodes):
    '''Node describing a schedule'''
    bl_idname = 'EnViSched'
    bl_label = 'Schedule'
    bl_icon = 'SOUND'

    def tupdate(self, context):
        try:
            err = 0
            if self.t2 <= self.t1 and self.t1 < 365:
                self.t2 = self.t1 + 1
                if self.t3 <= self.t2 and self.t2 < 365:
                    self.t3 = self.t2 + 1
                    if self.t4 != 365:
                        self.t4 = 365

            tn = (self.t1, self.t2, self.t3, self.t4).index(365) + 1
            if max((self.t1, self.t2, self.t3, self.t4)[:tn]) != 365:
                err = 1
            if any([not f for f in (self.f1, self.f2, self.f3, self.f4)[:tn]]):
                err = 1
            if any([not u or len(u.split(';')) != len((self.f1, self.f2, self.f3, self.f4)[i].split(' ')) for i, u in enumerate((self.u1, self.u2, self.u3, self.u4)[:tn])]):
                err = 1

            for f in (self.f1, self.f2, self.f3, self.f4)[:tn]:
                for fd in f.split(' '):
                    if not fd or (fd and fd.upper() not in ("ALLDAYS", "WEEKDAYS", "WEEKENDS", "MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY", "ALLOTHERDAYS")):
                        err = 1

            for u in (self.u1, self.u2, self.u3, self.u4)[:tn]:
                for uf in u.split(';'):
                    for ud in uf.split(','):
                        if len(ud.split()[0].split(':')) != 2 or int(ud.split()[0].split(':')[0]) not in range(1, 25) or len(ud.split()[0].split(':')) != 2 or not ud.split()[0].split(':')[1].isdigit() or int(ud.split()[0].split(':')[1]) not in range(0, 60):
                            err = 1
            nodecolour(self, err)

        except:
            nodecolour(self, 1)

    (u1, u2, u3, u4) =  [bpy.props.StringProperty(name = "", description = "Valid entries (; separated for each 'For', comma separated for each day, space separated for each time value pair)", update = tupdate)] * 4
    (f1, f2, f3, f4) =  [bpy.props.StringProperty(name = "", description = "Valid entries (space separated): AllDays, Weekdays, Weekends, Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, Sunday, AllOtherDays", update = tupdate)] * 4
    (t1, t2, t3, t4) = [bpy.props.IntProperty(name = "", default = 365, min = 1, max = 365, update = tupdate)] * 4

    def init(self, context):
        self['nodeid'] = nodeid(self)
        self.outputs.new('EnViSchedSocket', 'Schedule')
        self['scheddict'] = {'TSPSchedule': 'Any Number', 'VASchedule': 'Fraction', 'Fan Schedule': 'Fraction', 'HSchedule': 'Temperature', 'CSchedule': 'Temperature'}
        self.tupdate(context)
        nodecolour(self, 1)

    def draw_buttons(self, context, layout):
        uvals, u = (1, self.u1, self.u2, self.u3, self.u4), 0
        tvals = (0, self.t1, self.t2, self.t3, self.t4)
        while uvals[u] and tvals[u] < 365:
            [newrow(layout, v[0], self, v[1]) for v in (('End day {}:'.format(u+1), 't'+str(u+1)), ('Fors:', 'f'+str(u+1)), ('Untils:', 'u'+str(u+1)))]
            u += 1

    def update(self):
        for sock in self.outputs:
            socklink(sock, self['nodeid'].split('@')[1])
        bpy.data.node_groups[self['nodeid'].split('@')[1]].interface_update(bpy.context)

    def epwrite(self, name, stype):
        schedtext = ''
        for tosock in [link.to_socket for link in self.outputs['Schedule'].links]:
            if not schedtext:
                ths = [self.t1, self.t2, self.t3, self.t4]
                fos = [fs for fs in (self.f1, self.f2, self.f3, self.f4) if fs]
                uns = [us for us in (self.u1, self.u2, self.u3, self.u4) if us]
                ts, fs, us = rettimes(ths, fos, uns)
                schedtext = epschedwrite(name, stype, ts, fs, us)
                return schedtext
        return schedtext

class EnViFanNode(bpy.types.Node, EnViNodes):
    '''Node describing a fan component'''
    bl_idname = 'EnViFan'
    bl_label = 'Envi Fan'
    bl_icon = 'SOUND'

    fantype = [("Volume", "Constant Volume", "Constant volume flow fan component")]
    fantypeprop = bpy.props.EnumProperty(name="Type", description="Linkage type", items=fantype, default='Volume')
    fname = bpy.props.StringProperty(default = "", name = "")
    (feff, fpr, fmfr, fmeff, fmaf) = [bpy.props.FloatProperty(default = d, name = "") for d in (0.7, 600.0, 1.9, 0.9, 1.0)]

    def init(self, context):
        self.inputs.new('EnViCAirSocket', 'Extract from')
        self.inputs.new('EnViCAirSocket', 'Supply to')
        self.outputs.new('NodeSocket', 'Schedule')
        self.outputs.new('EnViCAirSocket', 'Extract from')
        self.outputs.new('EnViCAirSocket', 'Supply to')

    def update(self):
        try:
            fsocknames = ('Extract from', 'Supply to')
            for ins in [insock for insock in self.inputs if insock.name in fsocknames]:
                self.outputs[ins.name].hide = True if ins.is_linked else False
            for outs in [outsock for outsock in self.outputs if outsock.name in fsocknames]:
                self.inputs[outs.name].hide = True if outs.is_linked else False
        except:
            pass

    def draw_buttons(self, context, layout):
        layout.prop(self, 'fantypeprop')
        if self.fantypeprop == "Volume":
            vals = (("Name:", 'fname'), ("Efficiency:", 'feff'), ("Pressure Rise (Pa):", 'fpr'), ("Max flow rate:", 'fmfr'), ("Motor efficiency:", 'fmeff'), ("Airstream fraction:",'fmaf'))
            [newrow(layout, val[0], self, val[1]) for val in vals]

class EnViProgNode(bpy.types.Node, EnViNodes):
    '''Node describing an EMS Program'''
    bl_idname = 'EnViProg'
    bl_label = 'Envi Program'
    bl_icon = 'SOUND'

    text_file = bpy.props.StringProperty(description="Textfile to show")

    def init(self, context):
        self['nodeid'] = nodeid(self)
        self.outputs.new('EnViSenseSocket', 'Sensor')
        self.outputs.new('EnViActSocket', 'Actuator')
        nodecolour(self, 1)

    def draw_buttons(self, context, layout):
        layout.prop_search(self, 'text_file', bpy.data, 'texts', text='File', icon='TEXT')

    def update(self):
        for sock in self.outputs:
            socklink(sock, self['nodeid'].split('@')[1])
        nodecolour(self, not all([sock.links for sock in self.outputs]))

    def epwrite(self):
        sentries = ''
        for slink in self.outputs['Sensor'].links:
            snode = slink.to_node
            sparams = ('Name', 'Output:Variable or Output:Meter Index Key Name', 'EnergyManagementSystem:Sensor')
            if snode.bl_idname == 'EnViEMSZone':
                sparamvs = ('{}_{}'.format(snode.emszone, snode.sensordict[snode.sensortype][0]), '{}'.format(snode.emszone), snode.sensordict[snode.sensortype][1])
#                sentries += epentry('EnergyManagementSystem:Sensor', sparams, sparamvs)
            elif snode.bl_label == 'EnViOcc':
                for zlink in snode.outputs['Occupancy'].links:
                    znode = zlink.to_node
                    sparamvs = ('{}_{}'.format(znode.zone, snode.sensordict[snode.sensortype][0]), '{}'.format(znode.zone), snode.sensordict[snode.sensortype][1])
            sentries += epentry('EnergyManagementSystem:Sensor', sparams, sparamvs)

        aentries = ''
        for alink in self.outputs['Actuator'].links:
            anode, asocket = alink.to_node, alink.to_socket
            aparams = ('Name', 'Actuated Component Unique Name', 'Actuated Component Type', 'Actuated Component Control Type')
            aparamvs = (asocket.name, asocket.sn, anode.compdict[anode.acttype], anode.actdict[anode.acttype][0])
            aentries += epentry('EnergyManagementSystem:Actuator', aparams, aparamvs)

        cmparams = ('Name', 'EnergyPlus Model Calling Point', 'Program Name 1')
        cmparamvs = (self.name.replace(' ', '_'), 'BeginTimestepBeforePredictor', '{}_controller'.format(self.name.replace(' ', '_')))
        cmentry = epentry('EnergyManagementSystem:ProgramCallingManager', cmparams, cmparamvs)
        pparams = ['Name'] + ['line{}'.format(l) for l, line in enumerate(bpy.data.texts[self.text_file].lines) if line.body and line.body.strip()[0] != '!']
        pparamvs = ['{}_controller'.format(self.name.replace(' ', '_'))] + [line.body.strip() for line in bpy.data.texts[self.text_file].lines if line.body and line.body.strip()[0] != '!']
        pentry = epentry('EnergyManagementSystem:Program', pparams, pparamvs)
        return sentries + aentries + cmentry + pentry

class EnViEMSZoneNode(bpy.types.Node, EnViNodes):
    '''Node describing a simulation zone'''
    bl_idname = 'EnViEMSZone'
    bl_label = 'EMS Zone'
    bl_icon = 'SOUND'

    def supdate(self, context):
        self.inputs[0].name = '{}_{}'.format(self.emszone, self.sensordict[self.sensortype][0])

    def zupdate(self, context):
        adict = {'Window': 'win', 'Door': 'door'}
        self.supdate(context)
        try:
            obj = bpy.data.objects[self.emszone]
            odm = obj.data.materials
            sssocklist = ['{}_{}_{}_{}'.format(adict[odm[face.material_index].envi_con_type], self.emszone, face.index, self.actdict[self.acttype][1]) for face in obj.data.polygons if odm[face.material_index].envi_afsurface == 1 and odm[face.material_index].envi_con_type in ('Window', 'Door')]          
            self.inputs[0].hide = False
            nodecolour(self, 0)
        except:
            sssocklist = []
            self.inputs[0].hide = True
            nodecolour(self, 1)

        for iname in [inputs for inputs in self.inputs if inputs.name not in sssocklist and inputs.bl_idname == 'EnViActSocket']:
            try: self.inputs.remove(iname)
            except: pass

        for sock in sorted(set(sssocklist)):
            if not self.inputs.get(sock):
                try: self.inputs.new('EnViActSocket', sock).sn = '{0[0]}-{0[1]}_{0[2]}_{0[3]}'.format(sock.split('_'))
                except Exception as e: print('3190', e)

    emszone = bpy.props.StringProperty(name = '', update = zupdate)
    sensorlist = [("0", "Zone Temperature", "Sense the zone temperature"), ("1", "Zone Humidity", "Sense the zone humidity"), ("2", "Zone CO2", "Sense the zone CO2"),
                  ("3", "Zone Occupancy", "Sense the zone occupancy"), ("4", "Zone Equipment", "Sense the equipment level")]
    sensortype = bpy.props.EnumProperty(name="", description="Linkage type", items=sensorlist, default='0', update = supdate)
    sensordict = {'0':  ('Temp', 'Zone Mean Air Temperature'), '1': ('RH', 'Zone Air Relative Humidity'), '2': ('CO2', 'AFN Node CO2 Concentration')}
    actlist = [("0", "Opening factor", "Actuate the opening factor"), ("1", "Air supply temp", "Actuate an ideal air load system supply temperature"),
               ("2", "Air supply flow", "Actuate an ideal air load system flow rate"), ("3", "Outdoor Air supply flow", "Actuate an ideal air load system outdoor air flow rate")]
    acttype = bpy.props.EnumProperty(name="", description="Actuator type", items=actlist, default='0')
    compdict = {'0': 'AirFlow Network Window/Door Opening'}
    actdict =  {'0': ('Venting Opening Factor', 'of')}

    def init(self, context):
        self['nodeid'] = nodeid(self)
        self.inputs.new('EnViSenseSocket', 'Sensor')
        self.inputs[0].hide = True
        nodecolour(self, 1)

    def draw_buttons(self, context, layout):
        newrow(layout, 'Zone:', self, "emszone")
        if self.emszone in [o.name for o in bpy.data.objects]:
            newrow(layout, 'Sensor', self, 'sensortype')
        if len(self.inputs) > 1:
            newrow(layout, 'Actuator', self, 'acttype')

class EnViNodeCategory(NodeCategory):
    @classmethod
    def poll(cls, context):
        return context.space_data.tree_type == 'EnViN'

envinode_categories = [
        EnViNodeCategory("Control", "Control Node", items=[NodeItem("AFNCon", label="Control Node"), NodeItem("EnViWPCA", label="WPCA Node"), NodeItem("EnViCrRef", label="Crack Reference")]),
        EnViNodeCategory("Nodes", "Zone Nodes", items=[NodeItem("EnViZone", label="Zone Node"), NodeItem("EnViExt", label="External Node"), NodeItem("EnViOcc", label="Ocupancy Node")
        , NodeItem("EnViEq", label="Equipment Node"), NodeItem("EnViHvac", label="HVAC Node"), NodeItem("EnViInf", label="Infiltration Node"), NodeItem("EnViTC", label="Thermal Chimney Node")]),
        EnViNodeCategory("LinkNodes", "Airflow Link Nodes", items=[
            NodeItem("EnViSSFlow", label="Sub-surface Flow Node"), NodeItem("EnViSFlow", label="Surface Flow Node")]),
        EnViNodeCategory("SchedNodes", "Schedule Nodes", items=[NodeItem("EnViSched", label="Schedule")]),
        EnViNodeCategory("EMSNodes", "EMS Nodes", items=[NodeItem("EnViProg", label="Program"), NodeItem("EnViEMSZone", label="Zone")])]

class ViASCImport(bpy.types.Node, ViNodes):
    '''Node describing a LiVi geometry export node'''
    bl_idname = 'ViASCImport'
    bl_label = 'Vi ASC Import'
    bl_icon = 'LAMP'

    splitmesh = bpy.props.BoolProperty()
    single = bpy.props.BoolProperty(default = False)
    ascfile = bpy.props.StringProperty()

    def init(self, context):
        self['nodeid'] = nodeid(self)

    def draw_buttons(self, context, layout):
        row = layout.row()
        row.prop(self, 'single')
        if not self.single:
            row = layout.row()
            row.prop(self, 'splitmesh')
        row = layout.row()
        row.operator('node.ascimport', text = 'Import ASC').nodeid = self['nodeid']

