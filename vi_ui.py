import bpy, datetime
from collections import OrderedDict
from .vi_func import newrow, newrow2

from .envi_mat import envi_materials, envi_constructions
from .vi_func import retdates
envi_mats = envi_materials()
envi_cons = envi_constructions()

class Vi3DPanel(bpy.types.Panel):
    '''VI-Suite 3D view panel'''
    bl_label = "VI-Suite Display"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
        
    def draw(self, context):
        scene = context.scene
        cao = context.active_object
        layout = self.layout

        if scene.get('viparams') and cao and cao.active_material and cao.active_material.get('bsdf') and cao.active_material['bsdf']['type'] == ' ':
            if scene['viparams']['vidisp'] != 'bsdf_panel':
                row = layout.row()
                row.operator("view3d.bsdf_display", text="BSDF Display") 
            else:
                newrow(layout, 'BSDF max:', scene, "vi_bsdfleg_max")
                newrow(layout, 'BSDF min:', scene, "vi_bsdfleg_min")
                newrow(layout, 'BSDF scale:', scene, "vi_leg_scale")
                newrow(layout, 'BSDF colour:', scene, "vi_leg_col")

        if scene.get('viparams') and scene['viparams'].get('vidisp'): 
            if scene['viparams']['vidisp'] == 'wr' and 'Wind_Plane' in [o['VIType'] for o in bpy.data.objects if o.get('VIType')]:
                row = layout.row()
                row.operator('view3d.wrdisplay', text = 'Wind Metrics')#('INVOKE_DEFAULT'')
                
            elif scene['viparams']['vidisp'] == 'wrpanel' and scene.vi_display:
                newrow(layout, 'Wind metric:', scene, 'wind_type')
                newrow(layout, 'Colour:', scene, 'vi_leg_col')
                
            elif scene['viparams']['vidisp'] == 'sp' and scene.vi_display:
                (sdate, edate) = retdates(scene.solday, 365, 2015)
                for i in (("Day of year: {}/{}".format(sdate.day, sdate.month), "solday"), ("Time of day:", "solhour"), ("Display hours:", "hourdisp"), ("Display time:", "timedisp")):
                    newrow(layout, i[0], scene, i[1])
                if scene.hourdisp or scene.timedisp:
                    for i in (("Font size:", "vi_display_rp_fs"), ("Font colour:", "vi_display_rp_fc"), ("Font shadow:", "vi_display_rp_sh"), ("Shadow colour:", "vi_display_rp_fsh")):
                        newrow(layout, i[0], scene, i[1])
                
            elif scene['viparams']['vidisp'] in ('ss', 'li', 'lc'):
                row = layout.row()
                row.prop(scene, "vi_disp_3d")                 
                row = layout.row()
                if scene['viparams']['vidisp'] == 'ss':
                    row.operator("view3d.ssdisplay", text="Shadow Display")
                else:
                    row.operator("view3d.livibasicdisplay", text="Radiance Display")

            elif scene['viparams']['vidisp'] in ('sspanel', 'lipanel', 'lcpanel') and [o for o in bpy.data.objects if o.lires] and scene.vi_display:
                row = layout.row()
                row.prop(context.space_data, "show_only_render")

                if not scene.ss_disp_panel:
                    if scene['viparams']['visimcontext'] == 'LiVi CBDM':
                        if scene['liparams']['unit'] in ('DA (%)', 'sDA (%)', 'UDI-f (%)', 'UDI-s (%)', 'UDI-a (%)', 'UDI-e (%)', 'ASE (hrs)', 'Min lux', 'Max lux', 'Ave lux'):
                            newrow(layout, 'Result type:', scene, "li_disp_da")
                        elif scene['liparams']['unit'] in ('Mlxh', u'kWh/m\u00b2 (f)', u'kWh/m\u00b2 (v)', 'kWh (f)', 'kWh (v)'):
                            newrow(layout, 'Result type:', scene, "li_disp_exp")
                        elif scene['liparams']['unit'] in ('kWh', 'kWh/m2'):
                            newrow(layout, 'Result type:', scene, "li_disp_irrad")

                    elif scene['viparams']['visimcontext'] == 'LiVi Compliance': 
                        if scene['liparams']['unit'] in ('sDA (%)', 'ASE (hrs)'):
                            newrow(layout, 'Metric:', scene, 'li_disp_sda')

                        else:
                            newrow(layout, 'Metric:', scene, 'li_disp_sv')
                    elif scene['viparams']['visimcontext'] == 'LiVi Basic':
                        newrow(layout, 'Metric:', scene, 'li_disp_basic')
                        
                    newrow(layout, 'Legend max:', scene, "vi_leg_max")
                    newrow(layout, 'Legend min:', scene, "vi_leg_min")
                    newrow(layout, 'Legend scale:', scene, "vi_leg_scale")
                    newrow(layout, 'Legend colour:', scene, "vi_leg_col")
                    
                    if scene['liparams']['unit'] in ('DA (%)', 'sDA (%)', 'UDI-f (%)', 'UDI-s (%)', 'UDI-a (%)', 'UDI-e (%)', 'ASE (hrs)', 'Max lux', 'Ave lux', 'Min lux', 'kWh', 'kWh/m2'):
                        newrow(layout, 'Scatter max:', scene, "vi_scatter_max")
                        newrow(layout, 'Scatter min:', scene, "vi_scatter_min")
                
                if cao and cao.type == 'MESH':
                    newrow(layout, 'Draw wire:', scene, 'vi_disp_wire')                    
                
                if int(context.scene.vi_disp_3d) == 1:
                    newrow(layout, "3D Level", scene, "vi_disp_3dlevel")                        
                
                newrow(layout, "Transparency", scene, "vi_disp_trans")

                if context.mode != "EDIT":
                    row = layout.row()
                    row.label(text="{:-<48}".format("Point visualisation "))
                    propdict = OrderedDict([('Enable', "vi_display_rp"), ("Selected only:", "vi_display_sel_only"), ("Visible only:", "vi_display_vis_only"), ("Font size:", "vi_display_rp_fs"), ("Font colour:", "vi_display_rp_fc"), ("Font shadow:", "vi_display_rp_sh"), ("Shadow colour:", "vi_display_rp_fsh"), ("Position offset:", "vi_display_rp_off")])
                    for prop in propdict.items():
                        newrow(layout, prop[0], scene, prop[1])
                    row = layout.row()
                    row.label(text="{:-<60}".format(""))
 
            elif scene['viparams']['vidisp'] in ('en', 'enpanel'):
                fs, fe = scene['enparams']['fs'], scene['enparams']['fe']
                sedt = scene.en_disp_type
                resnode = bpy.data.node_groups[scene['viparams']['resnode'].split('@')[1]].nodes[scene['viparams']['resnode'].split('@')[0]]

                if sedt == '1':
                    zresdict = {}
                    lmetrics = []
                    vresdict = {"Max Flow in": "resazlmaxf_disp", "Min Flow in": "resazlminf_disp", "Ave Flow in": "resazlavef_disp"} 
                else: 
                    lmetrics, zmetrics = scene['enparams']['lmetrics'], scene['enparams']['zmetrics']
                    zresdict = {"Temperature (degC)": "reszt_disp", 'Humidity (%)': 'reszh_disp', 'Heating (W)': 'reszhw_disp', 'Cooling (W)': 'reszcw_disp', 
                                'CO2 (ppm)': 'reszco_disp', 'PMV': 'reszpmv_disp', 'PPD (%)': 'reszppd_disp', 'Solar gain (W)': 'reszsg_disp', 
                                'Air heating (W)': 'reszahw_disp', 'Air cooling (W)': 'reszacw_disp', 'HR heating (W)': 'reshrhw_disp'}
                    vresdict = {"Opening Factor": "reszof_disp", "Linkage Flow in": "reszlf_disp"}  

                if scene['viparams']['vidisp'] == 'en': 
                    newrow(layout, 'Static/Parametric', scene, 'en_disp_type')
                    if sedt == '1':
                        row = layout.row()               
                        row.prop(resnode, '["AStart"]')
                        row.prop(resnode, '["AEnd"]')
                    else:  
                        if fe > fs:                        
                            newrow(layout, 'Frame:', resnode, '["AStart"]')

                        row = layout.row() 
                        row.label(text = 'Start/End day:')
                        row.prop(resnode, '["Start"]')
                        row.prop(resnode, '["End"]')
                        row = layout.row() 
                        row.label(text = 'Ambient')
                        row = layout.row() 
                        row.prop(scene, 'resaa_disp')
                        row.prop(scene, 'resas_disp')
                        
                        for ri, rzname in enumerate(zmetrics):
                            if ri == 0:                    
                                row = layout.row()
                                row.label(text = 'Zone')                    
                            if not ri%2:
                                row = layout.row()  
                            if rzname in zresdict:
                                row.prop(scene, zresdict[rzname])
                        
                        for ri, rname in enumerate(lmetrics):
                            if ri == 0:                    
                                row = layout.row()
                                row.label(text = 'Ventilation')                    
                            if not ri%2:
                                row = layout.row()                            
                            if rname in vresdict:
                                row.prop(scene, vresdict[rname])  
                        if lmetrics:    
                            newrow(layout, 'Link to object', scene, 'envi_flink')  
                        
                        row = layout.row() 
   
                    if sedt == '0':
                        row.operator("view3d.endisplay", text="EnVi Display")
                    elif sedt == '1':
                        row.operator("view3d.enpdisplay", text="EnVi Display")
                        
            if scene['viparams']['vidisp'] == 'enpanel':                                
                if sedt == '0':
                    newrow(layout, 'Display unit:', scene, 'en_disp_unit')  
                    newrow(layout, 'Bar colour:', scene, "vi_leg_col")

                    if fe > fs:
                        newrow(layout, 'Parametric frame:', resnode, '["AStart"]')

                    envimenudict = {'Temperature (degC)': ('en_temp_min', 'en_temp_max'), 'Humidity (%)' : ('en_hum_min', 'en_hum_max'), 'Heating (W)': ('en_heat_min', 'en_heat_max'),
                                'Cooling (W)': ('en_cool_min', 'en_cool_max'), 'Solar gain (W)': ('en_shg_min', 'en_shg_max'), 'CO2 (ppm)': ('en_co2_min', 'en_co2_max'),
                                'PMV': ('en_pmv_min', 'en_pmv_max'), 'PPD (%)': ('en_ppd_min', 'en_ppd_max'), 'Air heating (W)': ('en_aheat_min', 'en_aheat_max'), 
                                'Air cooling (W)': ('en_acool_min', 'en_acool_max'), 'HR heating (W)': ('en_hrheat_min', 'en_hrheat_max'), 'Heat balance (W)': ('en_heatb_min', 'en_heatb_max'),
                                'Occupancy': ('en_occ_min', 'en_occ_max'), 'Infiltration (ACH)': ('en_iach_min', 'en_iach_max'), 'Infiltration (m3/s)': ('en_im3s_min', 'en_im3s_max')}
               
                    for envirt in envimenudict:
                        if envirt in zmetrics:
                            row = layout.row()
                            row.label(envirt)
                            row.prop(scene, envimenudict[envirt][0])
                            row.prop(scene, envimenudict[envirt][1])
                
                elif sedt == '1':
                    newrow(layout, 'Display unit:', scene, 'en_disp_punit')  
                    newrow(layout, 'Legend colour:', scene, "vi_leg_col")
                    row = layout.row()
                    row.label('Bar chart range:')
                    row.prop(scene, 'bar_min')
                    row.prop(scene, 'bar_max')
                                            
            if scene.vi_display:            
                newrow(layout, 'Display active', scene, 'vi_display')
        
            
class VIMatPanel(bpy.types.Panel):
    bl_label = "VI-Suite Material"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "material"

    @classmethod
    def poll(cls, context):
        return context.material

    def draw(self, context):
        cm, scene = context.material, context.scene
        layout = self.layout
        newrow(layout, 'Material type', cm, "mattype")
        if cm.mattype == '0':
            rmmenu(layout, cm)
            newrow(layout, "EnVi Construction Type:", cm, "envi_con_type")
            row = layout.row()
            if cm.envi_con_type not in ("Aperture", "Shading", "None"):
                newrow(layout, 'Intrazone Boundary', cm, "envi_boundary")
                newrow(layout, 'Airflow surface:', cm, "envi_afsurface")
                if not cm.envi_boundary and not cm.envi_afsurface:
                    newrow(layout, 'Thermal mass:', cm, "envi_thermalmass")
                newrow(layout, "Construction Make-up:", cm, "envi_con_makeup")
                if cm.envi_con_makeup == '1':
                    newrow(layout, "Outside layer:", cm, "envi_layero")
                    row = layout.row()
                    if cm.envi_layero == '1':
                        newrow(layout, "Outer layer type:", cm, "envi_type_lo")
                        newrow(layout, "Outer layer material:", cm, "envi_material_lo")
                        newrow(layout, "Outer layer thickness:", cm, "envi_export_lo_thi")
                            
                    elif cm.envi_layero == '2' and cm.envi_con_type != 'Window':
                        for end in ('name', 0, 'thi', 'tc', 0, 'rho', 'shc', 0, 'tab', 'sab', 0, 'vab', 'rough'):
                            if end:
                                row.prop(cm, '{}{}'.format("envi_export_lo_", end))
                            else:
                                row = layout.row()
                        if cm.envi_type_lo == '8':
                            newrow(layout, "TCTC:", cm, "envi_tctc_lo")
                            newrow(layout, "Temps:Enthalpies:", cm, "envi_tempsemps_lo")
    
                    elif cm.envi_layero == '2' and cm.envi_con_type == 'Window':
                        newrow(layout, "Name:", cm, "envi_export_lo_name")
                        newrow(layout, "Optical data type:", cm, "envi_export_lo_odt")
                        newrow(layout, "Construction Make-up:", cm, "envi_export_lo_sds")
                        newrow(layout, "Translucent:", cm, "envi_export_lo_sdiff")
                        for end in (0, 'thi', 'tc', 0, 'stn', 'fsn', 'bsn', 0, 'vtn', 'fvrn', 'bvrn', 0, 'itn', 'fie', 'bie'):
                            if end:
                                row.prop(cm, '{}{}'.format("envi_export_lo_", end))
                            else:
                                row = layout.row()
    
                    if cm.envi_layero != '0':
                        row = layout.row()
                        row.label("----------------")
                        newrow(layout, "2nd layer:", cm, "envi_layer1")
                        row = layout.row()
                        if cm.envi_layer1 == '1':
                            newrow(layout, "Second layer type:", cm, "envi_type_l1")
                            newrow(layout, "Second layer material:", cm, "envi_material_l1")
                            newrow(layout, "Second layer thickness:", cm, "envi_export_l1_thi")
                        
                        elif cm.envi_layer1 == '2' and cm.envi_con_type != 'Window':
                            for end in ('name', 0, 'thi', 'tc', 0, 'rho', 'shc', 0, 'tab', 'sab', 0, 'vab', 'rough'):
                                if end:
                                    row.prop(cm, '{}{}'.format("envi_export_l1_", end))
                                else:
                                    row = layout.row()
                            
                            if cm.envi_type_l1 == '8':
                                newrow(layout, "TCTC:", cm, "envi_tctc_l1")
                                newrow(layout, "Temps:Enthalpies:", cm, "envi_tempsemps_l1")
    
                        elif cm.envi_layer1 == '2' and cm.envi_con_type == 'Window':
                            newrow(layout, "Name:", cm, "envi_export_l1_name")
                            newrow(layout, "Gas Type:", cm, "envi_export_wgaslist_l1")
                            newrow(layout, "Gas thickness:", cm, "envi_export_l1_thi")
    
                        if cm.envi_layer1 != '0':
                            row = layout.row()
                            row.label("----------------")
                            row = layout.row()
                            row.label("3rd layer:")
                            row.prop(cm, "envi_layer2")
                            if cm.envi_layer2 == '1':
                                newrow(layout, "Third layer type:", cm, "envi_type_l2")
                                newrow(layout, "Third layer material:", cm, "envi_material_l2")
                                newrow(layout, "Third layer thickness:", cm, "envi_export_l2_thi")
    
                            elif cm.envi_layer2 == '2'and cm.envi_con_type != 'Window':
                                for end in ('name', 0, 'thi', 'tc', 0, 'rho', 'shc', 0, 'tab', 'sab', 0, 'vab', 'rough'):
                                    if end:
                                        row.prop(cm, '{}{}'.format("envi_export_l2_", end))
                                    else:
                                        row = layout.row()
                                        
                                if cm.envi_type_l2 == '8':
                                    newrow(layout, "TCTC:", cm, "envi_tctc_l2")
                                    newrow(layout, "Temps:Enthalpies:", cm, "envi_tempsemps_l2")
    
                            if cm.envi_layer2 == '2' and cm.envi_con_type == 'Window':
                                newrow(layout, "Name:", cm, "envi_export_l2_name")
                                newrow(layout, "Optical data type:", cm, "envi_export_l2_odt")
                                newrow(layout, "Construction Make-up:", cm, "envi_export_l2_sds")
                                newrow(layout, "Translucent:", cm, "envi_export_l2_sdiff")
                                for end in (0, 'thi', 'tc', 0, 'stn', 'fsn', 'bsn', 0, 'vtn', 'fvrn', 'bvrn', 0, 'itn', 'fie', 'bie'):
                                    if end:
                                        row.prop(cm, '{}{}'.format("envi_export_l2_", end))
                                    else:
                                        row = layout.row()
    
                            if cm.envi_layer2 != '0':
                                row = layout.row()
                                row.label("----------------")
                                row = layout.row()
                                row.label("4th layer:")
                                row.prop(cm, "envi_layer3")
                                row = layout.row()
                                if cm.envi_layer3 == '1':
                                    newrow(layout, "Fourth layer type:", cm, "envi_type_l3")
                                    newrow(layout, "Fourth layer material:", cm, "envi_material_l3")
                                    newrow(layout, "Fourth layer thickness:", cm, "envi_export_l3_thi")
    
                                elif cm.envi_layer3 == '2'and cm.envi_con_type != 'Window':
                                    for end in ('name', 0, 'thi', 'tc', 0, 'rho', 'shc', 0, 'tab', 'sab', 0, 'vab', 'rough'):
                                        if end:
                                            row.prop(cm, '{}{}'.format("envi_export_l3_", end))
                                        else:
                                            row = layout.row()
                                    
                                    if cm.envi_type_l3 == '8':
                                        newrow(layout, "TCTC:", cm, "envi_tctc_l3")
                                        newrow(layout, "Temps:Enthalpies:", cm, "envi_tempsemps_l3")
    
                                elif cm.envi_layer3 == '2' and cm.envi_con_type == 'Window':
                                    newrow(layout, "Name:", cm, "envi_export_l3_name")
                                    row = layout.row()
                                    row.label("Gas Type:")
                                    row.prop(cm, "envi_export_wgaslist_l3")
                                    newrow(layout, "3rd layer thickness:", cm, "envi_export_l3_thi")
    
                                if cm.envi_layer3 != '0':
                                    row = layout.row()
                                    row.label("----------------")
                                    row = layout.row()
                                    row.label("5th layer:")
                                    row.prop(cm, "envi_layer4")
                                    row = layout.row()
                                    if cm.envi_layer4 == '1':
                                        newrow(layout, "Fifth layer type:", cm, "envi_type_l4")
                                        newrow(layout, "Fifth layer material:", cm, "envi_material_l4")
                                        newrow(layout, "Fifth layer thickness:", cm, "envi_export_l4_thi")
    
                                    elif cm.envi_layer4 == '2' and cm.envi_con_type != 'Window':
                                        for end in ('name', 0, 'thi', 'tc', 0, 'rho', 'shc', 0, 'tab', 'sab', 0, 'vab', 'rough'):
                                            if end:
                                                row.prop(cm, '{}{}'.format("envi_export_l4_", end))
                                            else:
                                                row = layout.row()
                                        
                                        if cm.envi_type_l4 == '8':
                                            newrow(layout, "TCTC:", cm, "envi_tctc_l4")
                                            newrow(layout, "Temps:Enthalpies:", cm, "envi_tempsemps_l4")
    
                                    elif cm.envi_layer4 == '2' and cm.envi_con_type == 'Window':
                                        newrow(layout, "Name:", cm, "envi_export_l4_name")
                                        newrow(layout, "Optical data type:", cm, "envi_export_l4_odt")
                                        newrow(layout, "Construction Make-up:", cm, "envi_export_l4_sds")
                                        newrow(layout, "Translucent:", cm, "envi_export_l4_sdiff")
                                        for end in (0, 'thi', 'tc', 0, 'stn', 'fsn', 'bsn', 0, 'vtn', 'fvrn', 'bvrn', 0, 'itn', 'fie', 'bie'):
                                            if end:
                                                row.prop(cm, '{}{}'.format("envi_export_l4_", end))
                                            else:
                                                row = layout.row()
    
                elif cm.envi_con_makeup == '0':
                    thicklist = ("envi_export_lo_thi", "envi_export_l1_thi", "envi_export_l2_thi", "envi_export_l3_thi", "envi_export_l4_thi")
                    row = layout.row()                
                    row.prop(cm, 'envi_con_list')

                    for l, layername in enumerate(envi_cons.propdict[cm.envi_con_type][cm.envi_con_list]):    
                        row = layout.row()
                        row.label(text = layername)
                        if layername in envi_mats.wgas_dat:
                            row.prop(cm, thicklist[l])
                            row.label(text = "default: 14mm")
                        elif layername in envi_mats.gas_dat:
                            row.prop(cm, thicklist[l])
                            row.label(text = "default: 20-50mm")
                        elif layername in envi_mats.glass_dat:
                            row.prop(cm, thicklist[l])
                            row.label(text = "default: {}mm".format(float(envi_mats.matdat[layername][3])*1000))
                        else:
                            row.prop(cm, thicklist[l])
                            row.label(text = "default: {}mm".format(envi_mats.matdat[layername][7]))
        
        elif cm.mattype == '1':  
            if scene.get('viparams') and scene['viparams'].get('viexpcontext') and scene['viparams']['viexpcontext'] == 'LiVi Compliance':
                connode = bpy.data.node_groups[scene['viparams']['connode'].split('@')[1]].nodes[scene['viparams']['connode'].split('@')[0]]
                coptions = connode['Options']

                if coptions['canalysis'] == '0':
                    if coptions['bambuild'] == '2':
                        newrow(layout, "Space type:", cm, 'hspacemenu')
                    elif coptions['bambuild'] == '3':
                        newrow(layout, "Space type:", cm, 'brspacemenu')
                        if cm.brspacemenu == '2':
                            row = layout.row()
                            row.prop(cm, 'gl_roof')
                    elif coptions['bambuild'] == '4':
                        newrow(layout, "Space type:", cm, 'respacemenu')
                elif coptions['canalysis'] == '1':
                    newrow(layout, "Space type:", cm, 'crspacemenu')
                elif coptions['canalysis'] == '2':
                    if coptions['bambuild'] == '2':
                        newrow(layout, "Space type:", cm, 'hspacemenu')
                    if coptions['bambuild'] == '3':
                        newrow(layout, "Space type:", cm, 'brspacemenu')
#                    elif coptions['canalysis'] == '3':
#                        newrow(layout, "Space type:", cm, 'lespacemenu')                   
            rmmenu(layout, cm)
        
        elif cm.mattype == '2':
            fvsimnode = bpy.data.node_groups[scene['viparams']['fvsimnode'].split('@')[1]].nodes[scene['viparams']['fvsimnode'].split('@')[0]] if 'fvsimnode' in scene['viparams'] else 0
            newrow(layout, "Type:", cm, "flovi_bmb_type")
            if cm.flovi_bmb_type == '0':
                newrow(layout, "Pressure type:", cm, "flovi_bmwp_type")
                if cm.flovi_bmwp_type == 'fixedValue':
                    newrow(layout, "Pressure value:", cm, "flovi_b_sval")
                    
                newrow(layout, "Velocity type:", cm, "flovi_bmwu_type")
                newrow(layout, "Field value:", cm, "flovi_u_field")
                if not cm.flovi_u_field:
                    newrow(layout, 'Velocity:', cm, 'flovi_b_vval')
#                split = layout.split()
#                col = split.column(align=True)
#                col.label(text="Velocity:")
#                col.prop(cm, "flovi_bmu_x")
#                col.prop(cm, "flovi_bmu_y")
#                col.prop(cm, "flovi_bmu_z")
                
                if fvsimnode and fvsimnode.solver != 'icoFoam':
                    newrow(layout, "nut type:", cm, "flovi_bmwnut_type")
                    if fvsimnode.turbulence == 'SpalartAllmaras':                        
                        newrow(layout, "nuTilda type:", cm, "flovi_bmwnutilda_type")
                    elif fvsimnode.turbulence == 'kEpsilon':
                        newrow(layout, "k type:", cm, "flovi_bmwk_type")
                        newrow(layout, "Epsilon type:", cm, "flovi_bmwe_type")
                    elif fvsimnode.turbulence == 'komega':
                        newrow(layout, "k type:", cm, "flovi_bmwk_type")
                        newrow(layout, "Omega type:", cm, "flovi_bmwe_type")
                    if fvsimnode.bouyancy:
                        newrow(layout, "Temperature:", cm, "temperature")
#                newrow(layout, "nuTilda:", cm, "flovi_bmnutilda")
#                split = layout.split()
#                col = split.column(align=True)
#                col.label(text="nuTilda:")
#                col.prop(cm, "flovi_bmnut")
#                col.prop(cm, "flovi_bmwnut_y")
#                col.prop(cm, "flovi_bmwnut_z")
            elif cm.flovi_bmb_type == '1':
                newrow(layout, "Pressure sub-type:", cm, "flovi_bmip_type")
                if cm.flovi_bmip_type == 'fixedValue':
                    newrow(layout, "Pressure value:", cm, "flovi_b_sval")
                newrow(layout, "Velocity sub-type:", cm, "flovi_bmiu_type")
                newrow(layout, "Field value:", cm, "flovi_u_field")
                if not cm.flovi_u_field:
                    newrow(layout, 'Velocity:', cm, 'flovi_b_vval')
                if fvsimnode and fvsimnode.solver != 'icoFoam':
                    newrow(layout, "nut type:", cm, "flovi_bminut_type")
                    if fvsimnode.turbulence == 'SpalartAllmaras':                        
                        newrow(layout, "nuTilda type:", cm, "flovi_bminutilda_type")
                    elif fvsimnode.turbulence == 'kEpsilon':
                        newrow(layout, "k type:", cm, "flovi_bmik_type")
                        newrow(layout, "Epsilon type:", cm, "flovi_bmie_type")
                    elif fvsimnode.turbulence == 'kOmega':
                        newrow(layout, "k type:", cm, "flovi_bmik_type")
                        newrow(layout, "Omega type:", cm, "flovi_bmio_type")
            
            elif cm.flovi_bmb_type == '2':
                newrow(layout, "Pressure sub-type:", cm, "flovi_bmop_type")
                if cm.flovi_bmop_type == 'fixedValue':
                    newrow(layout, "Pressure value:", cm, "flovi_b_sval")
                newrow(layout, "Velocity sub-type:", cm, "flovi_bmou_type")
                newrow(layout, "Field value:", cm, "flovi_u_field")
                if not cm.flovi_u_field:
                    newrow(layout, 'Velocity:', cm, 'flovi_b_vval')
                if fvsimnode and fvsimnode.solver != 'icoFoam':
                    newrow(layout, "nut type:", cm, "flovi_bmonut_type")
                    if fvsimnode.turbulence == 'SpalartAllmaras':                        
                        newrow(layout, "nuTilda type:", cm, "flovi_bmonutilda_type")
                    elif fvsimnode.turbulence == 'kEpsilon':
                        newrow(layout, "k type:", cm, "flovi_bmok_type")
                        newrow(layout, "Epsilon type:", cm, "flovi_bmoe_type")
                    elif fvsimnode.turbulence == 'kOmega':
                        newrow(layout, "k type:", cm, "flovi_bmok_type")
                        newrow(layout, "Omega type:", cm, "flovi_bmoo_type")
                
class VIObPanel(bpy.types.Panel):
    bl_label = "VI-Suite Object Definition"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "data"

    @classmethod
    def poll(cls, context):
        if context.object and context.object.type in ('LAMP', 'MESH'):
            return True

    def draw(self, context):
        obj = context.active_object
        layout = self.layout

        if obj.type == 'MESH':
            row = layout.row()
            row.prop(obj, "vi_type")
            if obj.vi_type == '1':
                row = layout.row()
                row.prop(obj, "envi_type")
                if obj.envi_type == '0':
                    newrow(layout, 'Inside convection:', obj, "envi_ica")
                    newrow(layout, 'Outside convection:', obj, "envi_oca")
                    

        if (obj.type == 'LAMP' and obj.data.type != 'SUN') or obj.vi_type == '4':
            row = layout.row()
            row.operator("livi.ies_select")
            row.prop(obj, "ies_name")
            newrow(layout, 'IES Dimension:', obj, "ies_unit")
            newrow(layout, 'IES Strength:', obj, "ies_strength")
            row = layout.row()
            row.prop(obj, "ies_colour")

        elif obj.vi_type == '5':                
            newrow(layout, 'Direction:', obj, 'li_bsdf_direc')
            newrow(layout, 'Klems/Tensor:', obj, 'li_bsdf_tensor')
            if obj.li_bsdf_tensor != ' ':
                newrow(layout, 'resolution:', obj, 'li_bsdf_res')
                newrow(layout, 'Samples:', obj, 'li_bsdf_tsamp')
            else:
                newrow(layout, 'Samples:', obj, 'li_bsdf_ksamp')
            newrow(layout, 'RC params:', obj, 'li_bsdf_rcparam')
            
            if any([obj.data.materials[i].radmatmenu == '8' for i in [f.material_index for f in obj.data.polygons]]):
                row = layout.row()
                row.operator("object.gen_bsdf", text="Generate BSDF")
    
    #            if obj.get('bsdf'):
    #                row.operator("material.del_bsdf", text="Delete BSDF")
#                newrow(layout, 'Proxy:', obj, 'bsdf_proxy')

def rmmenu(layout, cm):
    row = layout.row()
    row.label('LiVi Radiance type:')
    row.prop(cm, 'radmatmenu')
    row = layout.row()

    for prop in cm.radmatdict[cm.radmatmenu]:
        if prop:
             row.prop(cm, prop)
        else:
            row = layout.row()
            
    if cm.radmatmenu == '8':
        newrow(layout, 'Proxy depth:', cm, 'li_bsdf_proxy_depth')
        row = layout.row()
        row.operator("material.load_bsdf", text="Load BSDF")
    elif cm.radmatmenu == '9':
        layout.prop_search(cm, 'radfile', bpy.data, 'texts', text='File', icon='TEXT')
    if cm.get('bsdf'):
        row.operator("material.del_bsdf", text="Delete BSDF")
        row = layout.row()
        row.operator("material.save_bsdf", text="Save BSDF")
    if cm.radmatmenu in ('1', '2', '3', '7'):
        newrow(layout, 'Photon Port:', cm, 'pport')
    if cm.radmatmenu in ('0', '1', '2', '3', '6'):
        newrow(layout, 'Textured:', cm, 'radtex')
        if cm.radtex:
            newrow(layout, 'Normal map:', cm, 'radnorm')
            if cm.radnorm:
                newrow(layout, 'Strength:', cm, 'ns')
                newrow(layout, 'Up vector:', cm, 'nu')
                newrow(layout, 'Green direction:', cm, 'gup')
    row = layout.row()
    row.label("-----------------------------------------")
    
class MESH_Gridify_Panel(bpy.types.Panel):
     bl_label = "Gridify Panel"
     bl_space_type = "VIEW_3D"
     bl_region_type = "TOOLS"
     bl_context = "objectmode"
     bl_category = "VI-Suite"
 
     def draw(self, context):         
         scene = context.scene
         layout = self.layout
         newrow(layout, 'Up vector:', scene, 'gridifyup')
         newrow(layout, 'Up size:', scene, 'gridifyus')
         newrow(layout, 'Across size:', scene, 'gridifyas')
         row = layout.row()
         row.operator("view3d.gridify", text="Grid the object")