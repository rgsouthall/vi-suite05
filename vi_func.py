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

import bpy, os, sys, multiprocessing, mathutils, bmesh, datetime, colorsys, bgl, blf, shlex, bpy_extras, math
#from collections import OrderedDict
from subprocess import Popen, PIPE, STDOUT
from numpy import int8, in1d, float32, float64, array, digitize, amax, amin, average, zeros, inner, transpose, nan, set_printoptions, choose, clip, where
set_printoptions(threshold=nan)
from numpy import sum as nsum
from numpy import max as nmax
from numpy import min as nmin
from numpy import mean as nmean
from numpy import delete as ndelete
from numpy import append as nappend
from math import sin, cos, asin, acos, pi, tan, ceil, log10
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
from xml.dom import minidom
from bpy.props import IntProperty, StringProperty, EnumProperty, FloatProperty, BoolProperty, FloatVectorProperty

try:
    import matplotlib
    if sys.platform == 'win32':
        matplotlib.use('Qt4Agg', force = True)
    else:
        matplotlib.use('Qt5Agg', force = True)
    import matplotlib.pyplot as plt
    import matplotlib.colors as colors
    import matplotlib.cm as mcm
    from .windrose import WindroseAxes
    mp = 1
except Exception as e:
    print(e)
    mp = 0

dtdf = datetime.date.fromordinal
unitdict = {'Lux': 'illu', u'W/m\u00b2 (f)': 'firrad', u'W/m\u00b2 (v)': 'virrad', 'DF (%)': 'df', 'DA (%)': 'da', 'UDI-f (%)': 'udilow', 'UDI-s (%)': 'udisup', 'UDI-a (%)': 'udiauto', 'UDI-e (%)': 'udihi',
            'Sky View': 'sv', 'Mlxh': 'illu', 'kWh (f)': 'firrad', 'kWh (v)': 'virrad', u'kWh/m\u00b2 (f)': 'firradm2', u'kWh/m\u00b2 (v)': 'virradm2', '% Sunlit': 'res', 'sDA (%)': 'sda', 'ASE (hrs)': 'ase', 'kW': 'watts', 'Max lux': 'illu', 
            'Ave lux': 'illu', 'Min lux': 'illu', 'kWh': 'kW', 'kWh/m2': 'kW/m2'}

coldict = {'0': 'rainbow', '1': 'gray', '2': 'hot', '3': 'CMRmap', '4': 'jet', '5': 'plasma'}

def retcols(scene, levels):
    try:
        cmap = mcm.get_cmap(scene.vi_leg_col)
        rgbas = [cmap(int(i * 255/(levels - 1))) for i in range(levels)]
    except:
        hs = [0.75 - 0.75*(i/19) for i in range(levels)]
        rgbas = [(*colorsys.hsv_to_rgb(h, 1.0, 1.0), 1.0) for h in hs]
    return rgbas
  
def cmap(scene):
    cols = retcols(scene, 20)
    for i in range(20):   
        matname = '{}#{}'.format('vi-suite', i)
        
        if not bpy.data.materials.get(matname):
            bpy.data.materials.new(matname)
            bpy.data.materials[matname].specular_intensity = 0
            bpy.data.materials[matname].specular_color = (0, 0, 0)
            bpy.data.materials[matname].use_shadeless = 0
        
#        if bpy.data.materials[matname].users:
        bpy.data.materials[matname].diffuse_color = cols[i][0:3]
        
def bmesh2mesh(scene, obmesh, o, frame, tmf):
    ftext, gradfile, vtext = '', '', ''

    try:
        bm = obmesh.copy()
#        bm.verts.ensure_lookup_table()
#        bm.faces.ensure_lookup_table()
        mrms = array([m.radmatmenu for m in o.data.materials])
        mpps = array([not m.pport for m in o.data.materials])        
        mnpps = where(mpps, 0, 1)        
        mmrms = in1d(mrms, array(('0', '1', '2', '3', '6', '9')))        
        fmrms = in1d(mrms, array(('0', '1', '2', '3', '6', '7', '9')), invert = True)
        mfaces = [f for f in bm.faces if (mmrms * mpps)[f.material_index]]
        ffaces = [f for f in bm.faces if (fmrms + mnpps)[f.material_index]]        
#        mfaces = [face for face in bm.faces if o.data.materials[face.material_index].radmatmenu in ('0', '1', '2', '3') and not o.data.materials[face.material_index].pport]
#        ffaces = [face for face in bm.faces if o.data.materials[face.material_index].radmatmenu not in ('0', '1', '2', '3', '7', '8') or o.data.materials[face.material_index].pport]    
        mmats = [mat for mat in o.data.materials if mat.radmatmenu in ('0', '1', '2', '3', '6', '9')]
        otext = 'o {}\n'.format(o.name)
        vtext = ''.join(['v {0[0]:.6f} {0[1]:.6f} {0[2]:.6f}\n'.format(v.co) for v in bm.verts])
        if o.data.polygons[0].use_smooth:
            vtext += ''.join(['vn {0[0]:.6f} {0[1]:.6f} {0[2]:.6f}\n'.format(v.normal.normalized()) for v in bm.verts])
        if not o.data.uv_layers:            
            if mfaces:
                for mat in mmats:
                    matname = mat.name.replace(' ', '_')
                    ftext += "usemtl {}\n".format(matname) + ''.join(['f {}\n'.format(' '.join(('{0}', '{0}//{0}')[f.smooth].format(v.index + 1) for v in f.verts)) for f in mfaces if o.data.materials[f.material_index] == mat])            
        else:            
            uv_layer = bm.loops.layers.uv.values()[0]
            bm.faces.ensure_lookup_table()
            vtext += ''.join([''.join(['vt {0[0]} {0[1]}\n'.format(loop[uv_layer].uv) for loop in face.loops]) for face in bm.faces])
            
            li = 1
            for face in bm.faces:
                for loop in face.loops:
                    loop.index = li
                    li +=1
                    
            if mfaces:
                for mat in mmats:
                    matname = mat.name.replace(' ', '_')
                    ftext += "usemtl {}\n".format(matname) + ''.join(['f {}\n'.format(' '.join(('{0}/{1}'.format(loop.vert.index + 1, loop.index), '{0}/{1}/{0}'.format(loop.vert.index + 1, loop.index))[f.smooth]  for loop in f.loops)) for f in mfaces if o.data.materials[f.material_index] == mat])

#        with open('/home/ryan/{}test.obj'.format(o.name), 'w') as ofile:
#            ofile.write(otext+vtext+ftext)                
        if ffaces:
            gradfile += radpoints(o, ffaces, 0)
    
        if ftext:   
            mfile = os.path.join(scene['viparams']['newdir'], 'obj', '{}-{}.mesh'.format(o.name.replace(' ', '_'), frame))

            with open(mfile, 'w') as mesh:
                o2mrun = Popen('obj2mesh -w -a {} '.format(tmf).split(), stdout = mesh, stdin = PIPE, stderr = PIPE).communicate(input = (otext + vtext + ftext).encode('utf-8'))

            if os.path.getsize(mfile) and not o2mrun[1]:
                gradfile += "void mesh id \n1 {}\n0\n0\n\n".format(mfile)
            else:
                gradfile += radpoints(o, mfaces, 0)

        bm.free()
            
        return gradfile
    
    except Exception as e:
        print(e)
        return gradfile
    
def radmat(self, scene):
    radname = self.name.replace(" ", "_")
    radtex = ''
    mod = 'void' 
    if self.radmatmenu in ('0', '1', '2', '3', '6') and self.radtex:
        try:
            teximage = self.node_tree.nodes['Material Output'].inputs['Surface'].links[0].from_node.inputs['Color'].links[0].from_node.image
            teximageloc = os.path.join(scene['liparams']['texfilebase'],'{}.hdr'.format(radname))
            off = scene.render.image_settings.file_format 
            scene.render.image_settings.file_format = 'HDR'
            teximage.save_render(teximageloc, scene)
            scene.render.image_settings.file_format = off
            (w, h) = teximage.size
            ar = ('*{}'.format(w/h), '') if w >= h else ('', '*{}'.format(h/w))
            radtex = 'void colorpict {}_tex\n7 red green blue {} . frac(Lu){} frac(Lv){}\n0\n0\n\n'.format(radname, '{}'.format(teximageloc), ar[0], ar[1])
            mod = '{}_tex'.format(radname)
            try:
                if self.radnorm:             
                    normimage = self.node_tree.nodes['Material Output'].inputs['Surface'].links[0].from_node.inputs['Normal'].links[0].from_node.inputs['Color'].links[0].from_node.image
                    header = '2\n0 1 {}\n0 1 {}\n'.format(normimage.size[1], normimage.size[0])
                    p = array(normimage.pixels[:])
                    totpix = normimage.size[0] * normimage.size[1]
                    xdat = (-1 + 2 * p.reshape(totpix, int(len(p)/totpix))[:,0]).reshape(normimage.size[0], normimage.size[1])                   
                    ydat = (-1 + 2 * p.reshape(totpix, int(len(p)/totpix))[:,1]).reshape(normimage.size[0], normimage.size[1]) if self.gup == '0' else (1 - 2 * p.reshape(totpix, int(len(p)/totpix))[:,1]).reshape(normimage.size[0], normimage.size[1])

                    with open(os.path.join(scene['liparams']['texfilebase'],'{}.ddx'.format(radname)), 'w') as xfile:
                        xfile.write(header + '\n'.join([' '.join(map(str, xd)) for xd in xdat]))
                    with open(os.path.join(scene['liparams']['texfilebase'],'{}.ddy'.format(radname)), 'w') as yfile:
                        yfile.write(header + '\n'.join([' '.join(map(str, xd)) for xd in ydat]))
                    radtex += "{0}_tex texdata {0}_norm\n9 ddx ddy ddz {1}.ddx {1}.ddy {1}.ddy nm.cal frac(Lv){2} frac(Lu){3}\n0\n4 {4} {5[0]} {5[1]} {5[2]}\n\n".format(radname, os.path.join(scene['viparams']['newdir'], 'textures', radname), ar[0], ar[1], self.ns, self.nu)
                    mod = '{}_norm'.format(radname)
                    
            except Exception as e:
                print('Problem with normal export {}'.format(e))
        except Exception as e:
            print('Problem with texture export {}'.format(e))
         
    radentry = '# ' + ('plastic', 'glass', 'dielectric', 'translucent', 'mirror', 'light', 'metal', 'antimatter', 'bsdf', 'custom')[int(self.radmatmenu)] + ' material\n' + \
            '{} {} {}\n'.format(mod, ('plastic', 'glass', 'dielectric', 'trans', 'mirror', 'light', 'metal', 'antimatter', 'bsdf', 'custom')[int(self.radmatmenu)], radname) + \
           {'0': '0\n0\n5 {0[0]:.3f} {0[1]:.3f} {0[2]:.3f} {1:.3f} {2:.3f}\n'.format(self.radcolour, self.radspec, self.radrough), 
            '1': '0\n0\n3 {0[0]:.3f} {0[1]:.3f} {0[2]:.3f}\n'.format(self.radcolour), 
            '2': '0\n0\n5 {0[0]:.3f} {0[1]:.3f} {0[2]:.3f} {1:.3f} 0\n'.format(self.radcolour, self.radior),
            '3': '0\n0\n7 {0[0]:.3f} {0[1]:.3f} {0[2]:.3f} {1:.3f} {2:.3f} {3:.3f} {4:.3f}\n'.format(self.radcolour, self.radspec, self.radrough, self.radtrans, self.radtranspec), 
            '4': '0\n0\n3 {0[0]:.3f} {0[1]:.3f} {0[2]:.3f}\n'.format(self.radcolour),
            '5': '0\n0\n3 {0[0]:.3f} {0[1]:.3f} {0[2]:.3f}\n'.format([c * self.radintensity for c in self.radcolour]), 
            '6': '0\n0\n5 {0[0]:.3f} {0[1]:.3f} {0[2]:.3f} {1:.3f} {2:.3f}\n'.format(self.radcolour, self.radspec, self.radrough), 
            '7': '1 void\n0\n0\n', '8': '1 void\n0\n0\n', '9': '1 void\n0\n0\n'}[self.radmatmenu] + '\n'

    if self.radmatmenu == '8' and self.get('bsdf') and self['bsdf'].get('xml'):
        bsdfxml = os.path.join(scene['viparams']['newdir'], 'bsdfs', '{}.xml'.format(radname))
        
        with open(bsdfxml, 'w') as bsdffile:
            bsdffile.write(self['bsdf']['xml'])
        radentry = 'void BSDF {0}\n6 {1:.4f} {2} 0 0 1 .\n0\n0\n\n'.format(radname, self.li_bsdf_proxy_depth, bsdfxml)
        
    elif self.radmatmenu == '9':
        radentry = bpy.data.texts[self.radfile].as_string()+'\n\n' if self.radfile in [t.name for t in bpy.data.texts] else '# dummy material\nvoid plastic {}\n0\n0\n5 0.8 0.8 0.8 0.1 0.1\n\n'.format(radname)
                        
    self['radentry'] = radtex + radentry
    return(radtex + radentry)
    
def radbsdf(self, radname, fi, rot, trans):
    fmat = self.data.materials[self.data.polygons[fi].material_index]
    pdepth = fmat['bsdf']['proxy_depth'] if self.bsdf_proxy else 0 
    bsdfxml = self.data.materials[self.data.polygons[fi].material_index]['bsdf']['xml']
    radname = '{}_{}_{}'.format(fmat.name, self.name, fi)
    radentry = 'void BSDF {0}\n16 {4:.4f} {1} 0 0 1 . -rx {2[0]:.4f} -ry {2[1]:.4f} -rz {2[2]:.4f} -t {3[0]:.4f} {3[1]:.4f} {3[2]:.4f}\n0\n0\n\n'.format(radname, bsdfxml, rot, trans, pdepth)
    return radentry
           
def rtpoints(self, bm, offset, frame):    
    geom = bm.verts if self['cpoint'] == '1' else bm.faces 
    cindex = geom.layers.int['cindex']
    rt = geom.layers.string['rt{}'.format(frame)]
    for gp in geom:
        gp[cindex] = 0 
    geom.ensure_lookup_table()
    resfaces = [face for face in bm.faces if self.data.materials[face.material_index].mattype == '1']
    self['cfaces'] = [face.index for face in resfaces]
       
    if self['cpoint'] == '0': 
        gpoints = resfaces
        gpcos =  [gp.calc_center_median_weighted() for gp in gpoints]
        self['cverts'], self['lisenseareas'][frame] = [], [f.calc_area() for f in gpoints]       

    elif self['cpoint'] == '1': 
        gis = sorted(set([item.index for sublist in [face.verts[:] for face in resfaces] for item in sublist]))
        gpoints = [geom[gi] for gi in gis]
        gpcos = [gp.co for gp in gpoints]
        self['cverts'], self['lisenseareas'][frame] = gp.index, [vertarea(bm, gp) for gp in gpoints]    
    
    for g, gp in enumerate(gpoints):
        gp[rt] = '{0[0]:.4f} {0[1]:.4f} {0[2]:.4f} {1[0]:.4f} {1[1]:.4f} {1[2]:.4f}'.format([gpcos[g][i] + offset * gp.normal.normalized()[i] for i in range(3)], gp.normal[:]).encode('utf-8')
        gp[cindex] = g + 1
        
    self['rtpnum'] = g + 1
                    
def regresults(scene, frames, simnode, res):    
    for i, f in enumerate(frames):
        simnode['maxres'][str(f)] = amax(res[i])
        simnode['minres'][str(f)] = amin(res[i])
        simnode['avres'][str(f)] = average(res[i])
    scene.vi_leg_max, scene.vi_leg_min = max(simnode['maxres'].values()), min(simnode['minres'].values()) 

def clearlayers(bm, ltype):
    if ltype in ('a', 'f'):
        while bm.faces.layers.float:
            bm.faces.layers.float.remove(bm.faces.layers.float[0])
        while bm.verts.layers.float:
            bm.verts.layers.float.remove(bm.verts.layers.float[0])
    if ltype in ('a', 's'):
        while bm.faces.layers.string:
            bm.faces.layers.string.remove(bm.faces.layers.string[0])
        while bm.verts.layers.string:
            bm.verts.layers.string.remove(bm.verts.layers.string[0])
    if ltype in ('a', 'i'):
        while bm.faces.layers.int:
            bm.faces.layers.int.remove(bm.faces.layers.int[0])
        while bm.verts.layers.string:
            bm.verts.layers.int.remove(bm.verts.layers.int[0])

def cbdmmtx(self, scene, locnode, export_op):
    os.chdir(scene['viparams']['newdir'])  
     
    if self['epwbase'][1] in (".epw", ".EPW"):
        with open(locnode.weather, "r") as epwfile:
            epwlines = epwfile.readlines()
            self['epwyear'] = epwlines[8].split(",")[0]
        Popen(("epw2wea", locnode.weather, "{}.wea".format(os.path.join(scene['viparams']['newdir'], self['epwbase'][0])))).wait()
        gdmcmd = ("gendaymtx -m 1 {} {}".format(('', '-O1')[self['watts']], "{0}.wea".format(os.path.join(scene['viparams']['newdir'], self['epwbase'][0]))))
        with open("{}.mtx".format(os.path.join(scene['viparams']['newdir'], self['epwbase'][0])), 'w') as mtxfile:
            Popen(gdmcmd.split(), stdout = mtxfile, stderr=STDOUT).communicate()
        with open("{}-whitesky.oct".format(scene['viparams']['filebase']), 'w') as wsfile:
            oconvcmd = "oconv -w -"
            Popen(shlex.split(oconvcmd), stdin = PIPE, stdout = wsfile).communicate(input = self['whitesky'].encode(sys.getfilesystemencoding()))
        return "{}.mtx".format(os.path.join(scene['viparams']['newdir'], self['epwbase'][0]))
    else:
        export_op.report({'ERROR'}, "Not a valid EPW file")
        return ''

def cbdmhdr(node, scene):
    targethdr = os.path.join(scene['viparams']['newdir'], node['epwbase'][0]+"{}.hdr".format(('l', 'w')[node['watts']]))
    latlonghdr = os.path.join(scene['viparams']['newdir'], node['epwbase'][0]+"{}p.hdr".format(('l', 'w')[node['watts']]))
    skyentry = hdrsky(targethdr, node.hdrmap, node.hdrangle, node.hdrradius)

    if node.sourcemenu != '1' or node.cbanalysismenu == '2':
        vecvals, vals = mtx2vals(open(node['mtxfile'], 'r').readlines(), datetime.datetime(2015, 1, 1).weekday(), node, node.times)
        pcombfiles = ''.join(["{} ".format(os.path.join(scene['viparams']['newdir'], 'ps{}.hdr'.format(i))) for i in range(146)])
        vwcmd = "vwrays -ff -x 600 -y 600 -vta -vp 0 0 0 -vd 0 1 0 -vu 0 0 1 -vh 360 -vv 360 -vo 0 -va 0 -vs 0 -vl 0"
        rcontribcmd = "rcontrib -bn 146 -fo -ab 0 -ad 1 -n {} -ffc -x 600 -y 600 -ld- -V+ -f tregenza.cal -b tbin -o {} -m sky_glow {}-whitesky.oct".format(scene['viparams']['nproc'], os.path.join(scene['viparams']['newdir'], 'p%d.hdr'), os.path.join(scene['viparams']['newdir'], scene['viparams']['filename']))
        vwrun = Popen(vwcmd.split(), stdout = PIPE)
        rcrun = Popen(rcontribcmd.split(), stderr = PIPE, stdin = vwrun.stdout)
        for line in rcrun.stderr:
            print(line)
    
        for j in range(146):
            with open(os.path.join(scene['viparams']['newdir'], "ps{}.hdr".format(j)), 'w') as psfile:
                Popen("pcomb -s {} {}".format(vals[j], os.path.join(scene['viparams']['newdir'], 'p{}.hdr'.format(j))).split(), stdout = psfile).wait()
        with open(targethdr, 'w') as epwhdr:
            Popen("pcomb -h {}".format(pcombfiles).split(), stdout = epwhdr).wait()
        
        [os.remove(os.path.join(scene['viparams']['newdir'], 'p{}.hdr'.format(i))) for i in range (146)]
        [os.remove(os.path.join(scene['viparams']['newdir'], 'ps{}.hdr'.format(i))) for i in range (146)]
        node.hdrname = targethdr
    
        if node.hdr:
            with open('{}.oct'.format(os.path.join(scene['viparams']['newdir'], node['epwbase'][0])), 'w') as hdroct:
                Popen(shlex.split("oconv -w - "), stdin = PIPE, stdout=hdroct, stderr=STDOUT).communicate(input = skyentry.encode(sys.filesystemencoding()))
            cntrun = Popen('cnt 750 1500'.split(), stdout = PIPE)
            rcalcrun = Popen('rcalc -f {} -e XD=1500;YD=750;inXD=0.000666;inYD=0.001333'.format(os.path.join(scene.vipath, 'Radfiles', 'lib', 'latlong.cal')).split(), stdin = cntrun.stdout, stdout = PIPE)
            with open(latlonghdr, 'w') as panohdr:
                rtcmd = 'rtrace -n {} -x 1500 -y 750 -fac {}.oct'.format(scene['viparams']['nproc'], os.path.join(scene['viparams']['newdir'], node['epwbase'][0]))
                Popen(rtcmd.split(), stdin = rcalcrun.stdout, stdout = panohdr)
    return skyentry

def retpmap(node, frame, scene):
    pportmats = ' '.join([mat.name.replace(" ", "_") for mat in bpy.data.materials if mat.pport and mat.get('radentry')])
    ammats = ' '.join([mat.name.replace(" ", "_") for mat in bpy.data.materials if mat.mattype == '1' and mat.radmatmenu == '7' and mat.get('radentry')])
    pportentry = '-apo {}'.format(pportmats) if pportmats else ''
    amentry = '-aps {}'.format(ammats) if ammats else ''
    cpentry = '-apc {}-{}.cpm {}'.format(scene['viparams']['filebase'], frame, node.pmapcno) if node.pmapcno else ''
    cpfileentry = '-ap {}-{}.cpm 50'.format(scene['viparams']['filebase'], frame) if node.pmapcno else ''  
    return amentry, pportentry, cpentry, cpfileentry     

def setscenelivivals(scene):
    scene['liparams']['maxres'], scene['liparams']['minres'], scene['liparams']['avres'] = {}, {}, {}
    cbdmunits = ('DA (%)', 'sDA (%)', 'UDI-f (%)', 'UDI-s (%)', 'UDI-a (%)', 'UDI-e (%)', 'ASE (hrs)', 'Max lux' , 'Ave lux', 'Min lux')
    expunits = ('Mlxh', "kWh (f)", "kWh (v)",  u'kWh/m\u00b2 (f)', u'kWh/m\u00b2 (v)', )
    irradunits = ('kWh', 'kWh/m2')

    if scene['viparams']['visimcontext'] == 'LiVi Basic':
        udict = {'0': 'Lux', '1': u'W/m\u00b2 (v)', '2': u'W/m\u00b2 (f)', '3': 'DF (%)'}
        scene['liparams']['unit'] = udict[scene.li_disp_basic]

    if scene['viparams']['visimcontext'] == 'LiVi CBDM':        
        if scene['liparams']['unit'] in cbdmunits:
            udict = {str(ui): u for ui, u in enumerate(cbdmunits)}
            scene['liparams']['unit'] = udict[scene.li_disp_da]
        if scene['liparams']['unit'] in expunits:
            udict = {str(ui): u for ui, u in enumerate(expunits)}
            scene['liparams']['unit'] = udict[scene.li_disp_exp]
        if scene['liparams']['unit'] in irradunits:
            udict = {str(ui): u for ui, u in enumerate(irradunits)}
            scene['liparams']['unit'] = udict[scene.li_disp_irrad]         

    if scene['viparams']['visimcontext'] == 'LiVi Compliance':
        if scene['liparams']['unit'] in cbdmunits:
            udict = {'0': 'sDA (%)', '1': 'ASE (hrs)'}
            scene['liparams']['unit'] = udict[scene.li_disp_sda]
        else:
            udict = {'0': 'DF (%)', '1': 'Sky View'}
            scene['liparams']['unit'] = udict[scene.li_disp_sv]
            
    olist = [scene.objects[on] for on in scene['liparams']['shadc']] if scene['viparams']['visimcontext'] == 'Shadow' else [scene.objects[on] for on in scene['liparams']['livic']]

    for frame in range(scene['liparams']['fs'], scene['liparams']['fe'] + 1):
        scene['liparams']['maxres'][str(frame)] = max([o['omax']['{}{}'.format(unitdict[scene['liparams']['unit']], frame)] for o in olist])
        scene['liparams']['minres'][str(frame)] = min([o['omin']['{}{}'.format(unitdict[scene['liparams']['unit']], frame)] for o in olist])
        scene['liparams']['avres'][str(frame)] = sum([o['oave']['{}{}'.format(unitdict[scene['liparams']['unit']], frame)] for o in olist])/len([o['oave']['{}{}'.format(unitdict[scene['liparams']['unit']], frame)] for o in olist])
    scene.vi_leg_max = max(scene['liparams']['maxres'].values())
    scene.vi_leg_min = min(scene['liparams']['minres'].values())
    
def rettree(scene, obs, ignore):
    bmob = bmesh.new()
    for soi, so in enumerate(obs):
        btemp = bpy.data.meshes.new("temp")
        bmtemp = bmesh.new()
        tempmesh = so.to_mesh(scene = scene, apply_modifiers = True, settings = 'PREVIEW')
        bmtemp.from_mesh(tempmesh)
        bpy.data.meshes.remove(tempmesh)
        bmtemp.transform(so.matrix_world)
        delfaces = [face for face in bmtemp.faces if so.data.materials[face.material_index].mattype == ignore]
        bmesh.ops.delete(bmtemp, geom = delfaces, context = 5)
        bmtemp.to_mesh(btemp)
        bmob.from_mesh(btemp)
        bpy.data.meshes.remove(btemp)
        
    tree = BVHTree.FromBMesh(bmob)
    bmob.free()
    bmtemp.free()
    return tree
    
class progressfile(): 
    def __init__(self, scene, starttime, calcsteps):
        self.starttime = starttime
        self.calcsteps = calcsteps
        self.scene = scene
        self.pfile = os.path.join(self.scene['viparams']['newdir'], 'viprogress')

        with open(self.pfile, 'w') as pfile:
            pfile.write('STARTING')
    
    def check(self, curres):
        with open(self.pfile, 'r') as pfile:
            if 'CANCELLED' in pfile.read():
                return 'CANCELLED'
                
        with open(os.path.join(self.scene['viparams']['newdir'], 'viprogress'), 'w') as pfile:
            if curres:
                dt = (datetime.datetime.now() - self.starttime) * (self.calcsteps - curres)/curres
                pfile.write('{} {}'.format(int(100 * curres/self.calcsteps), datetime.timedelta(seconds = dt.seconds)))
            else:
                pfile.write('0 Initialising')
        
def progressbar(file):
    kivytext = "# -*- coding: "+sys.getfilesystemencoding()+" -*-\n\
from kivy.app import App \n\
from kivy.clock import Clock \n\
from kivy.uix.progressbar import ProgressBar\n\
from kivy.uix.boxlayout import BoxLayout\n\
from kivy.uix.button import Button\n\
from kivy.uix.label import Label\n\
from kivy.config import Config\n\
Config.set('graphics', 'width', '500')\n\
Config.set('graphics', 'height', '200')\n\
\n\
class CancelButton(Button):\n\
    def on_touch_down(self, touch):\n\
        if 'button' in touch.profile:\n\
            if self.collide_point(*touch.pos):\n\
                with open(r'"+file+"', 'w') as pffile:\n\
                    pffile.write('CANCELLED')\n\
                App.get_running_app().stop()\n\
        else:\n\
            return\n\
    def on_open(self, widget, parent):\n\
        self.focus = True\n\
\n\
class Calculating(App):\n\
    bl = BoxLayout(orientation='vertical')\n\
    rpb = ProgressBar()\n\
    label = Label(text=' 0% Complete', font_size=20)\n\
    button = CancelButton(text='Cancel', font_size=20)\n\
    bl.add_widget(rpb)\n\
    bl.add_widget(label)\n\
    bl.add_widget(button)\n\
\n\
    def build(self):\n\
        refresh_time = 1\n\
        Clock.schedule_interval(self.timer, refresh_time)\n\
        return self.bl\n\
\n\
    def timer(self, dt):\n\
        with open(r'"+file+"', 'r') as pffile:\n\
            try:    (percent, tr) = pffile.readlines()[0].split()\n\
            except: percent, tr = 0, 'Not known'\n\
        self.rpb.value = int(percent)\n\
        self.label.text = '{}% Complete - Time remaining: {}'.format(percent, tr)\n\
\n\
if __name__ == '__main__':\n\
    Calculating().run()\n"

    with open(file+".py", 'w') as kivyfile:
        kivyfile.write(kivytext)
    return Popen([bpy.app.binary_path_python, file+".py"])

def logentry(text):
    log = bpy.data.texts.new('vi-suite-log') if 'vi-suite-log' not in bpy.data.texts else bpy.data.texts['vi-suite-log']
    log.write('')
    log.write('{}'.format(text))
    
def retsv(self, scene, frame, rtframe, chunk, rt):
    svcmd = "rcontrib -w -I -n {} {} -m sky_glow {}-{}.oct ".format(scene['viparams']['nproc'], '-ab 1 -ad 8192 -aa 0 -ar 512 -as 1024 -lw 0.0002 ', scene['viparams']['filebase'], frame)    
    rtrun = Popen(svcmd.split(), stdin = PIPE, stdout=PIPE, stderr=STDOUT, universal_newlines=True).communicate(input = '\n'.join([c[rt].decode('utf-8') for c in chunk]))                
    reslines = nsum(array([[float(rv) for rv in r.split('\t')[:3]] for r in rtrun[0].splitlines()[10:]]), axis = 1)
    reslines[reslines > 0] = 1
    return reslines.astype(int8)

def chunks(l, n):
    for v in range(0, len(l), n):
        yield l[v:v + n]
           
def basiccalcapply(self, scene, frames, rtcmds, simnode, curres, pfile):    
    reslists = []
    bm = bmesh.new()
    bm.from_mesh(self.data)
    bm.transform(self.matrix_world)
    self['omax'], self['omin'], self['oave'], self['livires'] = {}, {}, {}, {}
    clearlayers(bm, 'f')
    geom = bm.verts if self['cpoint'] == '1' else bm.faces
    cindex = geom.layers.int['cindex']
    totarea = sum([gp.calc_area() for gp in geom if gp[cindex] > 0]) if self['cpoint'] == '0' else sum([vertarea(bm, gp) for gp in geom])
    
    for f, frame in enumerate(frames):
        geom.layers.float.new('firrad{}'.format(frame))
        geom.layers.float.new('virrad{}'.format(frame))
        geom.layers.float.new('illu{}'.format(frame))
        geom.layers.float.new('df{}'.format(frame))
        geom.layers.float.new('res{}'.format(frame))
        firradres = geom.layers.float['firrad{}'.format(frame)]
        virradres = geom.layers.float['virrad{}'.format(frame)]
        illures = geom.layers.float['illu{}'.format(frame)]
        dfres = geom.layers.float['df{}'.format(frame)]
        res =  geom.layers.float['res{}'.format(frame)]
        
        if geom.layers.string.get('rt{}'.format(frame)):
            rtframe = frame
        else:
            kints = [int(k[2:]) for k in geom.layers.string.keys()]
            rtframe = max(kints) if frame > max(kints) else min(kints)
        
        rt =  geom.layers.string['rt{}'.format(rtframe)]
            
        for chunk in chunks([g for g in geom if g[rt]], int(scene['viparams']['nproc']) * 500):
            rtrun = Popen(rtcmds[f].split(), stdin = PIPE, stdout=PIPE, stderr=PIPE, universal_newlines=True).communicate(input = '\n'.join([c[rt].decode('utf-8') for c in chunk]))   
            xyzirrad = array([[float(v) for v in sl.split('\t')[:3]] for sl in rtrun[0].splitlines()]).astype(float32)
            virrad = nsum(xyzirrad * array([0.26, 0.67, 0.065], dtype = float32), axis = 1)
            firrad = virrad * 1.64
            illu = virrad * 179
            df = illu * 0.01
            for gi, gp in enumerate(chunk):
                gp[virradres] = virrad[gi]
                gp[firradres] = firrad[gi]
                gp[illures] = illu[gi]
                gp[dfres] = df[gi]
                gp[res] = illu[gi]
                
            curres += len(chunk)
            if pfile.check(curres) == 'CANCELLED':
                bm.free()
                return {'CANCELLED'}

        ovirrad = array([g[virradres] for g in geom], dtype = float32)
        maxovirrad, minovirrad, aveovirrad = nmax(ovirrad).astype(float64), nmin(ovirrad).astype(float64), nmean(ovirrad).astype(float64)
        self['omax']['virrad{}'.format(frame)] = maxovirrad
        self['omax']['illu{}'.format(frame)] =  maxovirrad * 179.0
        self['omax']['df{}'.format(frame)] =  maxovirrad * 1.79
        self['omax']['firrad{}'.format(frame)] =  maxovirrad * 1.64
        self['omin']['virrad{}'.format(frame)] = minovirrad
        self['omin']['illu{}'.format(frame)] = minovirrad * 179
        self['omin']['df{}'.format(frame)] = minovirrad * 1.79
        self['omin']['firrad{}'.format(frame)] = minovirrad * 1.64
        self['oave']['virrad{}'.format(frame)] = aveovirrad
        self['oave']['illu{}'.format(frame)] = aveovirrad * 179
        self['oave']['df{}'.format(frame)] = aveovirrad * 1.79
        self['oave']['firrad{}'.format(frame)] = aveovirrad
        tableheaders = [["", 'Minimum', 'Average', 'Maximum']]
        self['tableillu{}'.format(frame)] = array(tableheaders + [['Illuminance (lux)', '{:.1f}'.format(self['omin']['illu{}'.format(frame)]), '{:.1f}'.format(self['oave']['illu{}'.format(frame)]), '{:.1f}'.format(self['omax']['illu{}'.format(frame)])]])
        self['tabledf{}'.format(frame)] = array(tableheaders + [['DF (%)', '{:.1f}'.format(self['omin']['df{}'.format(frame)]), '{:.1f}'.format(self['oave']['df{}'.format(frame)]), '{:.1f}'.format(self['omax']['df{}'.format(frame)])]])
        self['tablevi{}'.format(frame)] = array(tableheaders + [['Visual Irradiance (W/m2)', '{:.1f}'.format(self['omin']['virrad{}'.format(frame)]), '{:.1f}'.format(self['oave']['virrad{}'.format(frame)]), '{:.1f}'.format(self['omax']['virrad{}'.format(frame)])]])
        self['tablefi{}'.format(frame)] = array(tableheaders + [['Full Irradiance (W/m2)', '{:.1f}'.format(self['omin']['firrad{}'.format(frame)]), '{:.1f}'.format(self['oave']['firrad{}'.format(frame)]), '{:.1f}'.format(self['omax']['firrad{}'.format(frame)])]])
        posis = [v.co for v in bm.verts if v[cindex] > 0] if self['cpoint'] == '1' else [f.calc_center_bounds() for f in bm.faces if f[cindex] > 1]
        illubinvals = [self['omin']['illu{}'.format(frame)] + (self['omax']['illu{}'.format(frame)] - self['omin']['illu{}'.format(frame)])/20 * (i + 0.05) for i in range(20)]
        bins = array([0.05 * i for i in range(1, 20)])
        if self['omax']['illu{}'.format(frame)] > self['omin']['illu{}'.format(frame)]:
            vals = [(gp[illures] - self['omin']['illu{}'.format(frame)])/(self['omax']['illu{}'.format(frame)] - self['omin']['illu{}'.format(frame)]) for gp in geom]         
        else:
            vals = [1 for gp in geom]
        ais = digitize(vals, bins)
        rgeom = [g for g in geom if g[cindex] > 0]
        rareas = [gp.calc_area() for gp in geom] if self['cpoint'] == '0' else [vertarea(bm, gp) for gp in geom]
        sareas = zeros(20)
        for ai in range(20):
            sareas[ai] = sum([rareas[gi]/totarea for gi in range(len(rgeom)) if ais[gi] == ai])
                
        self['livires']['areabins'] = sareas
        self['livires']['valbins'] = illubinvals
        reslists.append([str(frame), 'Zone', self.name, 'X', ' '.join(['{:.3f}'.format(p[0]) for p in posis])])
        reslists.append([str(frame), 'Zone', self.name, 'Y', ' '.join(['{:.3f}'.format(p[1]) for p in posis])])
        reslists.append([str(frame), 'Zone', self.name, 'Z', ' '.join(['{:.3f}'.format(p[2]) for p in posis])])
        reslists.append([str(frame), 'Zone', self.name, 'Areas (m2)', ' '.join(['{:.3f}'.format(ra) for ra in rareas])])
        reslists.append([str(frame), 'Zone', self.name, 'Illuminance(lux)', ' '.join(['{:.3f}'.format(g[illures]) for g in rgeom])])
        reslists.append([str(frame), 'Zone', self.name, 'DF (%)', ' '.join(['{:.3f}'.format(g[dfres]) for g in rgeom])])
        reslists.append([str(frame), 'Zone', self.name, 'Full Irradiance (W/m2)', ' '.join(['{:.3f}'.format(g[firradres]) for g in rgeom])])
        reslists.append([str(frame), 'Zone', self.name, 'Visible Irradiance (W/m2)', ' '.join(['{:.3f}'.format(g[virradres]) for g in rgeom])])
   
    bm.transform(self.matrix_world.inverted())
    bm.to_mesh(self.data)
    bm.free()
    return reslists
    
def lhcalcapply(self, scene, frames, rtcmds, simnode, curres, pfile):
    reslists = []
    bm = bmesh.new()
    bm.from_mesh(self.data)
    self['omax'], self['omin'], self['oave'] = {}, {}, {}
    clearlayers(bm, 'f')
    geom = bm.verts if self['cpoint'] == '1' else bm.faces
    cindex = geom.layers.int['cindex']
    
    for f, frame in enumerate(frames): 
        geom.layers.float.new('firradm2{}'.format(frame))
        geom.layers.float.new('virradm2{}'.format(frame))
        geom.layers.float.new('firrad{}'.format(frame))
        geom.layers.float.new('virrad{}'.format(frame))
        geom.layers.float.new('illu{}'.format(frame))
        geom.layers.float.new('res{}'.format(frame))
        firradm2res = geom.layers.float['firradm2{}'.format(frame)]
        virradm2res = geom.layers.float['virradm2{}'.format(frame)]
        firradres = geom.layers.float['firrad{}'.format(frame)]
        virradres = geom.layers.float['virrad{}'.format(frame)]
        illures = geom.layers.float['illu{}'.format(frame)]
         
        if geom.layers.string.get('rt{}'.format(frame)):
            rtframe = frame
        else:
            kints = [int(k[2:]) for k in geom.layers.string.keys()]
            rtframe  = max(kints) if frame > max(kints) else  min(kints)
        
        rt = geom.layers.string['rt{}'.format(rtframe)]
        gps = [g for g in geom if g[rt]]
        areas = array([g.calc_area() for g in gps] if self['cpoint'] == '0' else [vertarea(bm, g) for g in gps], dtype = float32)

        for chunk in chunks(gps, int(scene['viparams']['nproc']) * 200):
            careas = array([c.calc_area() if self['cpoint'] == '0' else vertarea(bm, c) for c in chunk], dtype = float32)
            rtrun = Popen(rtcmds[f].split(), stdin = PIPE, stdout=PIPE, stderr=PIPE, universal_newlines=True).communicate(input = '\n'.join([c[rt].decode('utf-8') for c in chunk]))   
            xyzirrad = array([[float(v) for v in sl.split('\t')[:3]] for sl in rtrun[0].splitlines()]).astype(float32)
            virradm2 = nsum(xyzirrad * array([0.26, 0.67, 0.065], dtype = float32), axis = 1) * 1e-3
            virrad = virradm2 * careas
            firradm2 = virradm2 * 1.64
            firrad = firradm2 * careas
            illu = virradm2 * 179e-3

            for gi, gp in enumerate(chunk):
                gp[firradm2res] = firradm2[gi]
                gp[virradm2res] = virradm2[gi]
                gp[firradres] = firrad[gi]
                gp[virradres] = virrad[gi]
                gp[illures] = illu[gi]
            
            curres += len(chunk)
            if pfile.check(curres) == 'CANCELLED':
                bm.free()
                return {'CANCELLED'}
                
        ovirradm2 = array([g[virradm2res] for g in gps]).astype(float32)
        ovirrad = array([g[virradres] for g in gps]).astype(float32)
        maxovirradm2 = nmax(ovirradm2).astype(float64)
        maxovirrad = nmax(ovirrad).astype(float64)
        minovirradm2 = nmin(ovirradm2).astype(float64)
        minovirrad = nmin(ovirrad).astype(float64)
        aveovirradm2 = nmean(ovirradm2).astype(float64)
        aveovirrad = nmean(ovirrad).astype(float64)
        self['omax']['firrad{}'.format(frame)] = maxovirrad * 1.64
        self['omin']['firrad{}'.format(frame)] = minovirrad * 1.64
        self['oave']['firrad{}'.format(frame)] = aveovirrad * 1.64
        self['omax']['firradm2{}'.format(frame)] = maxovirradm2  * 1.64
        self['omin']['firradm2{}'.format(frame)] = minovirradm2  * 1.64
        self['oave']['firradm2{}'.format(frame)] = aveovirradm2  * 1.64
        self['omax']['virrad{}'.format(frame)] = maxovirrad
        self['omin']['virrad{}'.format(frame)] = minovirrad
        self['oave']['virrad{}'.format(frame)] = aveovirrad
        self['omax']['virradm2{}'.format(frame)] = maxovirradm2
        self['omin']['virradm2{}'.format(frame)] = minovirradm2
        self['oave']['virradm2{}'.format(frame)] = aveovirradm2
        self['omax']['illu{}'.format(frame)] = maxovirradm2 * 178e-3
        self['omin']['illu{}'.format(frame)] = minovirradm2 * 178e-3
        self['oave']['illu{}'.format(frame)] = aveovirradm2 * 178e-3
        self['tablemlxh{}'.format(frame)] = array([["", 'Minimum', 'Average', 'Maximum'], 
            ['Luxhours (Mlxh)', '{:.1f}'.format(self['omin']['illu{}'.format(frame)]), '{:.1f}'.format(self['oave']['illu{}'.format(frame)]), '{:.1f}'.format(self['omax']['illu{}'.format(frame)])]])
        self['tablefim2{}'.format(frame)] = array([["", 'Minimum', 'Average', 'Maximum'], 
            ['Full Irradiance (kWh/m2)', '{:.1f}'.format(self['omin']['firradm2{}'.format(frame)]), '{:.1f}'.format(self['oave']['firradm2{}'.format(frame)]), '{:.1f}'.format(self['omax']['firradm2{}'.format(frame)])]])
        self['tablevim2{}'.format(frame)] = array([["", 'Minimum', 'Average', 'Maximum'], 
            ['Visual Irradiance (kWh/m2)', '{:.1f}'.format(self['omin']['virradm2{}'.format(frame)]), '{:.1f}'.format(self['oave']['virradm2{}'.format(frame)]), '{:.1f}'.format(self['omax']['virradm2{}'.format(frame)])]])
        self['tablefi{}'.format(frame)] = array([["", 'Minimum', 'Average', 'Maximum'], 
            ['Full Irradiance (kWh)', '{:.1f}'.format(self['omin']['firrad{}'.format(frame)]), '{:.1f}'.format(self['oave']['firrad{}'.format(frame)]), '{:.1f}'.format(self['omax']['firrad{}'.format(frame)])]])
        self['tablevi{}'.format(frame)] = array([["", 'Minimum', 'Average', 'Maximum'], 
            ['Visual Irradiance (kWh)', '{:.1f}'.format(self['omin']['virrad{}'.format(frame)]), '{:.1f}'.format(self['oave']['virrad{}'.format(frame)]), '{:.1f}'.format(self['omax']['virrad{}'.format(frame)])]])

        posis = [v.co for v in bm.verts if v[cindex] > 0] if self['cpoint'] == '1' else [f.calc_center_bounds() for f in bm.faces if f[cindex] > 1]
        reslists.append([str(frame), 'Zone', self.name, 'X', ' '.join([str(p[0]) for p in posis])])
        reslists.append([str(frame), 'Zone', self.name, 'Y', ' '.join([str(p[0]) for p in posis])])
        reslists.append([str(frame), 'Zone', self.name, 'Z', ' '.join([str(p[0]) for p in posis])])
        reslists.append([str(frame), 'Zone', self.name, 'Area', ' '.join([str(a) for a in areas])])
        reslists.append([str(frame), 'Zone', self.name, 'Full irradiance', ' '.join([str(g[firradres]) for g in geom if g[cindex] > 0])])
        reslists.append([str(frame), 'Zone', self.name, 'Visible irradiance', ' '.join([str(g[virradres]) for g in geom if g[cindex] > 0])])
        reslists.append([str(frame), 'Zone', self.name, 'Illuminance (Mlxh)', ' '.join([str(g[illures]) for g in geom if g[cindex] > 0])])
    bm.to_mesh(self.data)
    bm.free()
    return reslists
                    
def compcalcapply(self, scene, frames, rtcmds, simnode, curres, pfile):  
    pfs, epfs = [[] for f in frames], [[] for f in frames]
    self['compmat'] = [material.name for material in self.data.materials if material.mattype == '1'][0]
    self['omax'], self['omin'], self['oave'] = {}, {}, {}
    self['crit'], self['ecrit'], spacetype = retcrits(simnode, self['compmat'])    
    comps, ecomps =  {str(f): [] for f in frames}, {str(f): [] for f in frames}
    crits, dfpass, edfpass = [], {str(f): 0 for f in frames}, {str(f): 0 for f in frames} 
    selobj(scene, self)
    bm = bmesh.new()
    bm.from_mesh(self.data)
    clearlayers(bm, 'f')
    geom = bm.verts if simnode['goptions']['cp'] == '1' else bm.faces
    reslen = len(geom)
    cindex = geom.layers.int['cindex']
    pf = ('Fail', 'Pass')

    for f, frame in enumerate(frames):
        reslists, scores, escores, metric, emetric = [], [], [], [], []
        geom.layers.float.new('sv{}'.format(frame))
        geom.layers.float.new('df{}'.format(frame))
        geom.layers.float.new('res{}'.format(frame))
        dfres = geom.layers.float['df{}'.format(frame)]
        svres = geom.layers.float['sv{}'.format(frame)]
        res = geom.layers.float['res{}'.format(frame)]
        
        if geom.layers.string.get('rt{}'.format(frame)):
            rtframe = frame
        else:
            kints = [int(k[2:]) for k in geom.layers.string.keys()]
            rtframe  = max(kints) if frame > max(kints) else  min(kints)
        
        rt = geom.layers.string['rt{}'.format(rtframe)]
        
        for chunk in chunks([g for g in geom if g[rt]], int(scene['viparams']['nproc']) * 50):
            rtrun = Popen(rtcmds[f].split(), stdin = PIPE, stdout=PIPE, stderr=PIPE, universal_newlines=True).communicate(input = '\n'.join([c[rt].decode('utf-8') for c in chunk]))   
            xyzirrad = array([[float(v) for v in sl.split('\t')[:3]] for sl in rtrun[0].splitlines()]).astype(float32)
            virrad = nsum(xyzirrad * array([0.26, 0.67, 0.065]), axis = 1)
            illu = virrad * 179
            df = illu * 0.01
            sv = self.retsv(scene, frame, rtframe, chunk, rt)

            for gi, gp in enumerate(chunk):
                gp[dfres] = df[gi]
                gp[svres] = sv[gi]
                gp[res] = illu[gi]
            
            curres += len(chunk)
            if pfile.check(curres) == 'CANCELLED':
                bm.free()
                return {'CANCELLED'}

        resillu = array([gp[res] for gp in geom if gp[cindex] > 0], dtype = float32)
        resdf = array([gp[dfres] for gp in geom if gp[cindex] > 0], dtype = float32)
        ressv = array([gp[svres] for gp in geom if gp[cindex] > 0], dtype = int8)
        
        self['omax']['df{}'.format(frame)] = nmax(resdf).astype(float64)
        self['omin']['df{}'.format(frame)] = nmin(resdf).astype(float64)
        self['oave']['df{}'.format(frame)] = nmean(resdf).astype(float64)
        self['omax']['sv{}'.format(frame)] =  1.0
        self['omin']['sv{}'.format(frame)] = 0.0
        self['oave']['sv{}'.format(frame)] = nmean(ressv)
        self['tabledf{}'.format(frame)] = array([["", 'Minimum', 'Average', 'Maximum'], 
            ['DF (%)', '{:.1f}'.format(self['omin']['df{}'.format(frame)]), '{:.1f}'.format(self['oave']['df{}'.format(frame)]), '{:.1f}'.format(self['omax']['df{}'.format(frame)])]])
        self['tablesv{}'.format(frame)] = array([['', '% area with', '% area without'], ['Sky View', '{:.1f}'.format(100 * nsum(ressv)/len(ressv)), '{:.1f}'.format(100 - 100 * nsum(ressv)/(len(ressv)))]])

        posis = [v.co for v in bm.verts if v[cindex] > 0] if self['cpoint'] == '1' else [f.calc_center_bounds() for f in bm.faces if f[cindex] > 1]
        reslists.append([str(frame), 'Zone', self.name, 'X', ' '.join([str(p[0]) for p in posis])])
        reslists.append([str(frame), 'Zone', self.name, 'Y', ' '.join([str(p[0]) for p in posis])])
        reslists.append([str(frame), 'Zone', self.name, 'Z', ' '.join([str(p[0]) for p in posis])])
        resdict = {'DF': resdf, 'Illuminance': resillu, 'Sky View': ressv}
        for unit in resdict:
            reslists.append([str(frame), 'Zone', self.name, unit, ' '.join([str(r) for r in resdict[unit]])])
        
        dftotarea, dfpassarea, edfpassarea, edftotarea = 0, 0, 0, 0
        oareas = self['lisenseareas'][str(frame)]
        oarea = sum(oareas)
        passarea = 0

        for c in self['crit']:
            if c[0] == 'Average':
                if c[2] == 'DF':
                    dfpass[str(frame)] = 1
                    dfpassarea = dfpassarea + oarea if sum(resdf)/reslen > float(c[3]) else dfpassarea
                    comps[str(frame)].append((0, 1)[sum(resdf)/reslen > float(c[3])])
                    comps[str(frame)].append(sum(resdf)/reslen)
                    dftotarea += oarea
                    metric.append(['Average DF', c[3], '{:.1f}'.format(comps[str(frame)][-1]), pf[comps[str(frame)][-2]]])
                    
            elif c[0] == 'Min':
                comps[str(frame)].append((0, 1)[min(resdf) > float(c[3])])
                comps[str(frame)].append(min(resdf))
                metric.append(['Minimum DF', c[3], '{:.1f}'.format(comps[str(frame)][-1]), pf[comps[str(frame)][-2]]])
    
            elif c[0] == 'Ratio':
                comps[str(frame)].append((0, 1)[min(resdf)/(sum(resdf)/reslen) >= float(c[3])])
                comps[str(frame)].append(min(resdf)/(sum(resdf)/reslen))
                metric.append(['Ratio of minimum to average DF', c[3], '{:.1f}'.format(comps[str(frame)][-1]), pf[comps[str(frame)][-2]]])
            
            elif c[0] == 'Percent':
                if c[2] == 'PDF':
                    dfpass[str(frame)] = 1
                    dfpassarea = sum([area for p, area in enumerate(oareas) if resdf[p] > int(c[3])])
                    comps[str(frame)].append((0, 1)[dfpassarea > float(c[1])*oarea/100])
                    comps[str(frame)].append(100*dfpassarea/oarea)
                    dftotarea += oarea
                    metric.append(['% area with Point DF > {}'.format(c[3]), c[1], '{:.1f}'.format(comps[str(frame)][-1]), pf[comps[str(frame)][-2]]])                    
                elif c[2] == 'Skyview': 
                    passarea = sum([area for p, area in enumerate(oareas) if ressv[p] > 0])
                    comps[str(frame)].append((0, 1)[passarea >= float(c[1])*oarea/100])
                    comps[str(frame)].append(100*passarea/oarea)
                    passarea = 0
                    metric.append(['% area with sky view', c[1], '{:.1f}'.format(comps[str(frame)][-1]), pf[comps[str(frame)][-2]]])
                elif c[2] == 'DF':  
                    passareapc = 100 * sum([area for p, area in enumerate(oareas) if resdf[p] > float(c[3])])/oarea
                    comps[str(frame)].append((0, 1)[sum([area * resdf[p] for p, area in enumerate(oareas)])/oarea > float(c[3])])
                    comps[str(frame)].append(sum([area * resdf[p] for p, area in enumerate(oareas)])/oarea)
                    metric.append(['% area with DF > {}'.format(c[3]), c[1], '{:.1f}'.format(passareapc), pf[passareapc >= float(c[1])]])
            scores.append(c[4])  

        passfails = [m[-1] for m in metric]

        if simnode['coptions']['canalysis'] == '0':
            if 'Pass' not in passfails:
                opf = 'FAIL'
            elif 'Fail' not in passfails:
                opf = 'PASS'
            elif 'Fail' in [c for i, c in enumerate(passfails) if scores[i] == '1']:
                opf = 'FAIL'
            elif 'Pass' not in [c for i, c in enumerate(passfails) if scores[i] == '0.75'] and len([c for i, c in enumerate(list(zip(metric))[-1]) if scores[i] == '0.75']) > 0:
                if 'Pass' not in [c for i, c in enumerate(passfails) if scores[i] == '0.5'] and len([c for i, c in enumerate(list(zip(metric))[-1]) if scores[i] == '0.5']) > 0:
                    opf = 'FAIL'
                else:
                    opf = 'PASS'
            else:
                opf = 'PASS'
            pfs[f].append(opf)
        
        elif simnode['coptions']['canalysis'] == '1':
            for met in metric:
                if self.data.materials[self['compmat']].crspacemenu == '0': # Kitchen Space
                
                    if met[0] == 'Average DF':
                        pfs[f].append((1, met[-1]))
                    else:
                        pfs[f].append((2, met[-1]))
                else: # Living Space
                    pfs[f].append((0, met[-1]))
                        
        elif simnode['coptions']['canalysis'] == '2':
            pfs[f] = [m[-1] for m in metric]

        if self['ecrit']:
            emetric = [['', '', '', ''], ['Exemplary requirements: ', '', '', '']]
        
            for e in self['ecrit']:
                if e[0] == 'Percent':
                    if e[2] == 'DF':
                        epassareapc = 100 * sum([area for p, area in enumerate(oareas) if resdf[p] > float(e[3])])/oarea
                        ecomps[str(frame)].append((0, 1)[sum([area * resdf[p] for p, area in enumerate(oareas)])/oarea > float(e[3])])
                        ecomps[str(frame)].append(sum([area * resdf[p] for p, area in enumerate(oareas)])/oarea)
                        emetric.append(['% area with DF > {}'.format(e[3]), e[1], '{:.1f}'.format(epassareapc), pf[epassareapc >= float(e[1])]])
                        
                    if e[2] == 'PDF':
                        edfpass[str(frame)] = 1
                        edfpassarea = sum([area for p, area in enumerate(oareas) if resdf[p] > float(e[3])])      
                        ecomps[str(frame)].append((0, 1)[dfpassarea > float(e[1])*oarea/100])
                        ecomps[str(frame)].append(100*edfpassarea/oarea)
                        edftotarea += oarea
                        emetric.append(['% area with Point DF > {}'.format(e[3]), e[1], '{:.1f}'.format(ecomps[str(frame)][-1]), pf[ecomps[str(frame)][-2]]])
        
                    elif e[2] == 'Skyview':
                        passarea = sum([area for p, area in enumerate(oareas) if ressv[p] > 0])
                        ecomps[str(frame)].append((0, 1)[passarea >= int(e[1]) * oarea/100])
                        ecomps[str(frame)].append(100*passarea/oarea)
                        passarea = 0
                        emetric.append(['% area with sky view', e[1], '{:.1f}'.format(ecomps[str(frame)][-1]), pf[ecomps[str(frame)][-2]]])
        
                elif e[0] == 'Min':
                    ecomps[str(frame)].append((0, 1)[min(resdf) > float(e[3])])
                    ecomps[str(frame)].append(min(resdf))
                    emetric.append(['Minimum DF', e[3], '{:.1f}'.format(ecomps[str(frame)][-1]), pf[ecomps[str(frame)][-2]]])
        
                elif e[0] == 'Ratio':
                    ecomps[str(frame)].append((0, 1)[min(resdf)/(sum(resdf)/reslen) >= float(e[3])])
                    ecomps[str(frame)].append(min(resdf)/(sum(resdf)/reslen))
                    emetric.append(['Ratio of minimum to average DF', e[3], '{:.1f}'.format(ecomps[str(frame)][-1]), pf[ecomps[str(frame)][-2]]])
        
                elif e[0] == 'Average':
                    ecomps[str(frame)].append((0, 1)[sum(resdf)/reslen > float(e[3])])
                    ecomps[str(frame)].append(sum(resdf)/reslen)
                    emetric.append(['% area with Average DF > {}'.format(e[3]), e[1], ecomps[str(frame)][-1], pf[ecomps[str(frame)][-2]]])
                crits.append(self['crit'])
                escores.append(e[4])
                
            epassfails = [em[-1] for em in emetric[2:]]

            if 'Pass' not in epassfails:
                epf = 'FAIL'     
            if 'Fail' not in epassfails:
                epf = 'PASS' 
            elif 'Fail' in [c for i, c in enumerate(epassfails) if escores[i] == '1']:
                epf = 'FAIL'
            elif 'Pass' not in [c for i, c in enumerate(epassfails) if escores[i] == '0.75'] and len([c for i, c in enumerate(list(zip(emetric))[-1]) if escores[i] == '0.75']) > 0:
                if 'Pass' not in [c for i, c in enumerate(epassfails) if escores[i] == '0.5'] and len([c for i, c in enumerate(list(zip(emetric))[-1]) if escores[i] == '0.5']) > 0:
                    epf = 'FAIL'
                else:
                    epf = 'EXEMPLARY'
            else:
                epf = 'EXEMPLARY'

            epfs[f].append(epf)
    
        if dfpass[str(frame)] == 1:
            dfpass[str(frame)] = 2 if dfpassarea/dftotarea >= (0.8, 0.35)[simnode['coptions']['canalysis'] == '0' and simnode['coptions']['buildtype'] == '4'] else dfpass[str(frame)]
        if edfpass[str(frame)] == 1:
            edfpass[str(frame)] = 2 if edfpassarea/edftotarea >= (0.8, 0.5)[simnode['coptions']['canalysis'] == '0' and simnode['coptions']['buildtype'] == '4'] else edfpass[str(frame)]
        
        smetric = [['Standard: {}'.format(('BREEAM HEA1', 'CfSH', 'Green Star', 'LEED EQ8.1')[int(simnode['coptions']['Type'])]), '', '', ''], 
                    ['Space type: {}'.format(spacetype), '', '', ''], ['', '', '', ''], ['Standard requirements:', 'Target', 'Result', 'Pass/Fail']] + metric
        self['tablecomp{}'.format(frame)] = smetric if not self['ecrit'] else smetric + emetric

    bm.to_mesh(self.data)
    bm.free()
    return (pfs, epfs, reslists)
    
def udidacalcapply(self, scene, frames, rccmds, simnode, curres, pfile):
    self['livires'] = {}
    selobj(scene, self)
    bm = bmesh.new()
    bm.from_mesh(self.data)
    bm.transform(self.matrix_world)
    clearlayers(bm, 'f')
    geom = bm.verts if self['cpoint'] == '1' else bm.faces
    reslen = len(geom)

    if self.get('wattres'):
        del self['wattres']
        
    illuarray = array((47.4, 120, 11.6)).astype(float32)
    vwattarray = array((0.265, 0.67, 0.065)).astype(float32)
    fwattarray = vwattarray * 1.64
    times = [datetime.datetime.strptime(time, "%d/%m/%y %H:%M:%S") for time in simnode['coptions']['times']]                          
    vecvals, vals = mtx2vals(open(simnode.inputs['Context in'].links[0].from_node['Options']['mtxfile'], 'r').readlines(), datetime.datetime(2010, 1, 1).weekday(), simnode, times)
    cbdm_days = [d for d in range(simnode['coptions']['sdoy'], simnode['coptions']['edoy'] + 1)] if scene['viparams']['visimcontext'] == 'LiVi CBDM' else [d for d in range(1, 366)]
    cbdm_hours = [h for h in range(simnode['coptions']['cbdm_sh'], simnode['coptions']['cbdm_eh'] + 1)]
    dno, hno = len(cbdm_days), len(cbdm_hours)    
    (luxmin, luxmax) = (simnode['coptions']['dalux'], simnode['coptions']['asemax']) if scene['viparams']['visimcontext'] != 'LiVi Compliance' else (300, 1000)
    vecvals = array([vv[2:] for vv in vecvals if vv[1] < simnode['coptions']['weekdays']]).astype(float32)
    hours = vecvals.shape[0]
    restypes = ('da', 'sda', 'ase', 'res', 'udilow', 'udisup', 'udiauto', 'udihi', 'kW', 'kW/m2', 'illu')
    self['livires']['cbdm_days'] = cbdm_days
    self['livires']['cbdm_hours'] = cbdm_hours

    for f, frame in enumerate(frames):        
        reslists = [[str(frame), 'Time', '', 'Month', ' '.join([str(t.month) for t in times])]]
        reslists.append([str(frame), 'Time', '', 'Day', ' '.join([str(t.day) for t in times])])
        reslists.append([str(frame), 'Time', '', 'Hour', ' '.join([str(t.hour) for t in times])])
        reslists.append([str(frame), 'Time', '', 'DOS', ' '.join([str(t.timetuple().tm_yday - times[0].timetuple().tm_yday) for t in times])])

        for restype in restypes:
            geom.layers.float.new('{}{}'.format(restype, frame))
        (resda, ressda, resase, res, resudilow, resudisup, resudiauto, resudihi, reskw, reskwm2, resillu) = [geom.layers.float['{}{}'.format(r, frame)] for r in restypes]

        if simnode['coptions']['buildtype'] == '1':
            geom.layers.float.new('sv{}'.format(frame))
            ressv = geom.layers.float['sv{}'.format(frame)]
        
        if geom.layers.string.get('rt{}'.format(frame)):
            rtframe = frame
        else:
            kints = [int(k[2:]) for k in geom.layers.string.keys()]
            rtframe  = max(kints) if frame > max(kints) else  min(kints)
        
        rt = geom.layers.string['rt{}'.format(rtframe)]
        totarea = sum([g.calc_area() for g in geom if g[rt]]) if self['cpoint'] == '0' else sum([vertarea(bm, g) for g in geom if g[rt]])
                
        for ch, chunk in enumerate(chunks([g for g in geom if g[rt]], int(scene['viparams']['nproc']) * 40)):
            sensrun = Popen(rccmds[f].split(), stdin=PIPE, stdout=PIPE, universal_newlines=True).communicate(input = '\n'.join([c[rt].decode('utf-8') for c in chunk]))
            resarray = array([[float(v) for v in sl.split('\t') if v] for sl in sensrun[0].splitlines() if sl not in ('\n', '\r\n')]).reshape(len(chunk), 146, 3).astype(float32)
            chareas = array([c.calc_area() for c in chunk]) if self['cpoint'] == '0' else array([vertarea(bm, c) for c in chunk]).astype(float32)
            sensarray = nsum(resarray*illuarray, axis = 2).astype(float32)
            wsensearray  = nsum(resarray*fwattarray, axis = 2).astype(float32)
            finalillu = inner(sensarray, vecvals).astype(float64)
            
            if scene['viparams']['visimcontext'] != 'LiVi Compliance':            
                finalwattm2 = inner(wsensearray, vecvals).astype(float32)
                wsensearraym2 = (wsensearray.T * chareas).T.astype(float32)
                finalwatt = inner(wsensearraym2, vecvals).astype(float32)  
                dabool = choose(finalillu >= simnode['coptions']['dalux'], [0, 1]).astype(int8)
                udilbool = choose(finalillu < simnode['coptions']['damin'], [0, 1]).astype(int8)
                udisbool = choose(finalillu < simnode['coptions']['dasupp'], [0, 1]).astype(int8) - udilbool
                udiabool = choose(finalillu < simnode['coptions']['daauto'], [0, 1]).astype(int8) - udilbool - udisbool
                udihbool = choose(finalillu >= simnode['coptions']['daauto'], [0, 1]).astype(int8)                       
                daareares = (dabool.T*chareas).T             
                udilareares = (udilbool.T*chareas).T
                udisareares = (udisbool.T*chareas).T
                udiaareares = (udiabool.T*chareas).T
                udihareares = (udihbool.T*chareas).T
                dares = dabool.sum(axis = 1)*100/hours
                udilow = udilbool.sum(axis = 1)*100/hours
                udisup = udisbool.sum(axis = 1)*100/hours
                udiauto = udiabool.sum(axis = 1)*100/hours
                udihi = udihbool.sum(axis = 1)*100/hours
                kwh = 0.001 * nsum(finalwatt, axis = 1)
                kwhm2 = 0.001 * nsum(finalwattm2, axis = 1)
            
            if scene['viparams']['visimcontext'] == 'LiVi Compliance' and simnode['coptions']['buildtype'] == '1':
                svres = self.retsv(scene, frame, rtframe, chunk, rt)
                sdaareas = where([sv > 0 for sv in svres], chareas, 0)
            else:
                sdaareas = chareas
            sdabool = choose(finalillu >= luxmin, [0, 1]).astype(int8)
            asebool = choose(finalillu >= luxmax, [0, 1]).astype(int8)
            aseareares = (asebool.T*chareas).T
            sdaareares = (sdabool.T*sdaareas).T            
            sdares = sdabool.sum(axis = 1)*100/hours
            aseres = asebool.sum(axis = 1)*1.0
                                    
            for gi, gp in enumerate(chunk):
                if scene['viparams']['visimcontext'] != 'LiVi Compliance':
                    gp[resda] = dares[gi]                
                    gp[res] = dares[gi]
                    gp[resudilow] = udilow[gi]
                    gp[resudisup] = udisup[gi]
                    gp[resudiauto] = udiauto[gi]
                    gp[resudihi] = udihi[gi]
                    gp[reskw] = kwh[gi]
                    gp[reskwm2] = kwhm2[gi]
                    gp[resillu] = max(finalillu[gi])
                
                elif simnode['coptions']['buildtype'] == '1':
                    gp[ressv] = svres[gi]
                gp[ressda] = sdares[gi]
                gp[resase] = aseres[gi]

            if not ch:
                if scene['viparams']['visimcontext'] != 'LiVi Compliance':
                    totfinalillu = finalillu
                    totdaarea = nsum(100 * daareares/totarea, axis = 0)
                    totudiaarea = nsum(100 * udiaareares/totarea, axis = 0)
                    totudisarea = nsum(100 * udisareares/totarea, axis = 0)
                    totudilarea = nsum(100 * udilareares/totarea, axis = 0)
                    totudiharea = nsum(100 * udihareares/totarea, axis = 0)                
                    
                if scene['viparams']['visimcontext'] == 'LiVi CBDM'  and simnode['coptions']['cbanalysis'] == '1':
                    totfinalwatt = nsum(finalwatt, axis = 0)#nsum(inner(sensarray, vecvals), axis = 0)
                    totfinalwattm2 = average(finalwattm2, axis = 0)
                else:
                    totsdaarea = nsum(sdaareares, axis = 0)
                    totasearea = nsum(aseareares, axis = 0)
            else:
                if scene['viparams']['visimcontext'] != 'LiVi Compliance':
                    nappend(totfinalillu, finalillu)
                    totdaarea += nsum(100 * daareares/totarea, axis = 0)
                    totudiaarea += nsum(100 * udiaareares/totarea, axis = 0)
                    totudilarea += nsum(100 * udilareares/totarea, axis = 0)
                    totudisarea += nsum(100 * udisareares/totarea, axis = 0)
                    totudiharea += nsum(100 * udihareares/totarea, axis = 0)
                if scene['viparams']['visimcontext'] == 'LiVi CBDM'  and simnode['coptions']['cbanalysis'] == '1':
                    totfinalwatt += nsum(finalwatt, axis = 0)#nsum(inner(sensarray, vecvals), axis = 0)
                    totfinalwattm2 += average(finalwattm2, axis = 0)
                else:
                    totsdaarea += nsum(sdaareares, axis = 0)
                    totasearea += nsum(aseareares, axis = 0)
              
            curres += len(chunk)
            if pfile.check(curres) == 'CANCELLED':
                bm.free()
                return {'CANCELLED'}

        if scene['viparams']['visimcontext'] != 'LiVi Compliance':
            dares = [gp[resda] for gp in geom] 
            udilow = [gp[resudilow] for gp in geom] 
            udisup = [gp[resudisup] for gp in geom]
            udiauto = [gp[resudiauto] for gp in geom]
            udihi = [gp[resudihi] for gp in geom]
            kwh = [gp[reskw] for gp in geom]
            kwhm2 = [gp[reskwm2] for gp in geom]
            self['omax']['udilow{}'.format(frame)] = max(udilow)
            self['omin']['udilow{}'.format(frame)] = min(udilow)
            self['oave']['udilow{}'.format(frame)] = sum(udilow)/reslen
            self['omax']['udisup{}'.format(frame)] = max(udisup)
            self['omin']['udisup{}'.format(frame)] = min(udisup)
            self['oave']['udisup{}'.format(frame)] = sum(udisup)/reslen
            self['omax']['udiauto{}'.format(frame)] = max(udiauto)
            self['omin']['udiauto{}'.format(frame)] = min(udiauto)
            self['oave']['udiauto{}'.format(frame)] = sum(udiauto)/reslen
            self['omax']['udihi{}'.format(frame)] = max(udihi)
            self['omin']['udihi{}'.format(frame)] = min(udihi)
            self['oave']['udihi{}'.format(frame)] = sum(udihi)/reslen
            self['omax']['da{}'.format(frame)] = max(dares)
            self['omin']['da{}'.format(frame)] = min(dares)
            self['oave']['da{}'.format(frame)] = sum(dares)/reslen
            self['omax']['illu{}'.format(frame)] = amax(totfinalillu)
            self['omin']['illu{}'.format(frame)] = amin(totfinalillu)
            self['oave']['illu{}'.format(frame)] = nmean(totfinalillu)/reslen
            self['livires']['dhilluave{}'.format(frame)] = average(totfinalillu, axis = 0).flatten().reshape(dno, hno).transpose()
            self['livires']['dhillumin{}'.format(frame)] = amin(totfinalillu, axis = 0).reshape(dno, hno).transpose()
            self['livires']['dhillumax{}'.format(frame)] = amax(totfinalillu, axis = 0).reshape(dno, hno).transpose()
            self['livires']['daarea{}'.format(frame)] = totdaarea.reshape(dno, hno).transpose()
            self['livires']['udiaarea{}'.format(frame)] = totudiaarea.reshape(dno, hno).transpose()
            self['livires']['udisarea{}'.format(frame)] = totudisarea.reshape(dno, hno).transpose()
            self['livires']['udilarea{}'.format(frame)] = totudilarea.reshape(dno, hno).transpose()
            self['livires']['udiharea{}'.format(frame)] = totudiharea.reshape(dno, hno).transpose() 
            
            self['tableudil{}'.format(frame)] = array([["", 'Minimum', 'Average', 'Maximum'], 
                ['UDI-l (% area)', '{:.1f}'.format(self['omin']['udilow{}'.format(frame)]), '{:.1f}'.format(self['oave']['udilow{}'.format(frame)]), '{:.1f}'.format(self['omax']['udilow{}'.format(frame)])]])
            self['tableudis{}'.format(frame)] = array([["", 'Minimum', 'Average', 'Maximum'], 
                ['UDI-s (% area)', '{:.1f}'.format(self['omin']['udisup{}'.format(frame)]), '{:.1f}'.format(self['oave']['udisup{}'.format(frame)]), '{:.1f}'.format(self['omax']['udisup{}'.format(frame)])]])
            self['tableudia{}'.format(frame)] = array([["", 'Minimum', 'Average', 'Maximum'], 
                ['UDI-a (% area)', '{:.1f}'.format(self['omin']['udiauto{}'.format(frame)]), '{:.1f}'.format(self['oave']['udiauto{}'.format(frame)]), '{:.1f}'.format(self['omax']['udiauto{}'.format(frame)])]])
            self['tableudie{}'.format(frame)] = array([["", 'Minimum', 'Average', 'Maximum'], 
                ['UDI-e (% area)', '{:.1f}'.format(self['omin']['udihi{}'.format(frame)]), '{:.1f}'.format(self['oave']['udihi{}'.format(frame)]), '{:.1f}'.format(self['omax']['udihi{}'.format(frame)])]])
            self['tableillu{}'.format(frame)] = array([["", 'Minimum', 'Average', 'Maximum'], 
                ['Illuminance (lux)', '{:.1f}'.format(self['omin']['illu{}'.format(frame)]), '{:.1f}'.format(self['oave']['illu{}'.format(frame)]), '{:.1f}'.format(self['omax']['illu{}'.format(frame)])]])
            self['tableda{}'.format(frame)] = array([["", 'Minimum', 'Average', 'Maximum'], 
                ['Daylight availability (% time)', '{:.1f}'.format(self['omin']['da{}'.format(frame)]), '{:.1f}'.format(self['oave']['da{}'.format(frame)]), '{:.1f}'.format(self['omax']['da{}'.format(frame)])]])
            
            reslists.append([str(frame), 'Zone', self.name, 'Daylight Autonomy Area (%)', ' '.join([str(p) for p in totdaarea])])
            reslists.append([str(frame), 'Zone', self.name, 'UDI-a Area (%)', ' '.join([str(p) for p in totudiaarea])])
            reslists.append([str(frame), 'Zone', self.name, 'UDI-s Area (%)', ' '.join([str(p) for p in totudisarea])])
            reslists.append([str(frame), 'Zone', self.name, 'UDI-l Area (%)', ' '.join([str(p) for p in totudilarea])])
            reslists.append([str(frame), 'Zone', self.name, 'UDI-h Area (%)', ' '.join([str(p) for p in totudiharea])])
        
        if scene['viparams']['visimcontext'] == 'LiVi CBDM' and simnode['coptions']['cbanalysis'] == '1': 
            self['omax']['kW{}'.format(frame)] = max(kwh)
            self['omin']['kW{}'.format(frame)] = min(kwh)
            self['oave']['kW{}'.format(frame)] = sum(kwh)/reslen
            self['omax']['kW/m2{}'.format(frame)] = max(kwhm2)
            self['omin']['kW/m2{}'.format(frame)] = min(kwhm2)
            self['oave']['kW/m2{}'.format(frame)] = sum(kwhm2)/reslen
            self['livires']['kW{}'.format(frame)] =  (0.001*totfinalwatt).reshape(dno, hno).transpose()
            self['livires']['kW/m2{}'.format(frame)] =  (0.001*totfinalwattm2).reshape(dno, hno).transpose()
            self['tablekwh{}'.format(frame)] = array([["", 'Minimum', 'Average', 'Maximum'], 
                ['Irradiance (kW)', '{:.1f}'.format(self['omin']['kW{}'.format(frame)]), '{:.1f}'.format(self['oave']['kW{}'.format(frame)]), '{:.1f}'.format(self['omax']['kW{}'.format(frame)])]])
            self['tablekwhm2{}'.format(frame)] = array([["", 'Minimum', 'Average', 'Maximum'], 
                ['Irradiance (kW/m2)', '{:.1f}'.format(self['omin']['kW/m2{}'.format(frame)]), '{:.1f}'.format(self['oave']['kW/m2{}'.format(frame)]), '{:.1f}'.format(self['omax']['kW/m2{}'.format(frame)])]])
            reslists.append([str(frame), 'Zone', self.name, 'kW', ' '.join([str(p) for p in 0.001 * totfinalwatt])])
            reslists.append([str(frame), 'Zone', self.name, 'kW/m2', ' '.join([str(p) for p in 0.001 * totfinalwattm2])])
        else:
            sdares = [gp[ressda] for gp in geom]
            aseres = [gp[resase] for gp in geom]
            if scene['viparams']['visimcontext'] == 'LiVi Compliance' and simnode['coptions']['buildtype'] == '1':
                overallsdaarea = sum([g.calc_area() for g in geom if g[rt] and g[ressv]]) if self['cpoint'] == '0' else sum([vertarea(bm, g) for g in geom if g[rt] and g[ressv]]) 
            else:
                overallsdaarea = totarea
            self['omax']['sda{}'.format(frame)] = max(sdares)
            self['omin']['sda{}'.format(frame)] = min(sdares)
            self['oave']['sda{}'.format(frame)] = sum(sdares)/reslen
            self['omax']['ase{}'.format(frame)] = max(aseres)
            self['omin']['ase{}'.format(frame)] = min(aseres)
            self['oave']['ase{}'.format(frame)] = sum(aseres)/reslen
            self['livires']['asearea{}'.format(frame)] = (100 * totasearea/totarea).reshape(dno, hno).transpose()
            self['livires']['sdaarea{}'.format(frame)] = (100 * totsdaarea/overallsdaarea).reshape(dno, hno).transpose()
            self['tablesda{}'.format(frame)] = array([["", 'Minimum', 'Average', 'Maximum'], 
                ['sDA (% hours)', '{:.1f}'.format(self['omin']['sda{}'.format(frame)]), '{:.1f}'.format(self['oave']['sda{}'.format(frame)]), '{:.1f}'.format(self['omax']['sda{}'.format(frame)])]])
            self['tablease{}'.format(frame)] = array([["", 'Minimum', 'Average', 'Maximum'], 
                ['ASE (hrs)', '{:.1f}'.format(self['omin']['ase{}'.format(frame)]), '{:.1f}'.format(self['oave']['ase{}'.format(frame)]), '{:.1f}'.format(self['omax']['ase{}'.format(frame)])]])
            reslists.append([str(frame), 'Zone', self.name, 'Annual Sunlight Exposure (% area)', ' '.join([str(p) for p in 100 * totasearea/totarea])])
            reslists.append([str(frame), 'Zone', self.name, 'Spatial Daylight Autonomy (% area)', ' '.join([str(p) for p in 100 * totsdaarea/overallsdaarea])])
            
        metric, scores, pf = [], [], ('Fail', 'Pass')

        if scene['viparams']['visimcontext'] == 'LiVi Compliance':
            self['crit'], self['ecrit'], spacetype = retcrits(simnode, self['compmat'])
            sdapassarea, asepassarea, comps = 0, 0, {str(f): [] for f in frames}
            oareas = self['lisenseareas'][str(frame)]
            oarea = sum(oareas)
            geom.ensure_lookup_table()
            hoarea = sum([oa for o, oa in enumerate(oareas) if geom[o][ressv] > 0]) if simnode['coptions']['buildtype'] == '3' else oarea
            aoarea = hoarea if simnode['coptions']['buildtype'] == '1' else oarea     
            self['oarea'] = aoarea

            for c in self['crit']:
                if c[0] == 'Percent':        
                    if c[2] == 'SDA':
                        sdapassarea = sum([area for p, area in enumerate(oareas) if sdares[p] >= 50 and svres[p] > 0]) if simnode['coptions']['buildtype'] == '1' else sum([area for p, area in enumerate(oareas) if sdares[p] >= 50])
                        comps[str(frame)].append((0, 1)[sdapassarea >= float(c[1])*oarea/100])
                        comps[str(frame)].append(100*sdapassarea/aoarea)
                        self['sdapassarea'] = sdapassarea
                        metric.append(['% area with SDA', c[1], '{:.1f}'.format(comps[str(frame)][-1]), pf[comps[str(frame)][-2]]])
                    
                    elif c[2] == 'ASE':
                        asepassarea = sum([area for p, area in enumerate(oareas) if aseres[p] > 250 and svres[p] > 0]) if simnode['coptions']['buildtype'] == '1' else sum([area for p, area in enumerate(oareas) if aseres[p] > 250])
                        comps[str(frame)].append((0, 1)[asepassarea <= float(c[1])*aoarea/100])
                        comps[str(frame)].append(100*asepassarea/aoarea)
                        self['asepassarea'] = asepassarea
                        metric.append(['% area with ASE', c[1], '{:.1f}'.format(comps[str(frame)][-1]), pf[comps[str(frame)][-2]]])
                    scores.append(c[4])

            self['comps'] = comps
            self['tablecomp{}'.format(frame)] = [['Standard: {}'.format('LEEDv4 EQ8.1'), '', '', ''], 
                ['Space type: {}'.format(spacetype), '', '', ''], ['', '', '', ''], ['Standard requirements:', 'Target', 'Result', 'Pass/Fail']] + metric
        
    bm.transform(self.matrix_world.inverted())        
    bm.to_mesh(self.data)
    bm.free()
    return [m[-1] for m in metric], scores, reslists

def retcrits(simnode, matname):
    ecrit = []
    mat = bpy.data.materials[matname]
    if simnode['coptions']['canalysis'] == '0':
        if simnode['coptions']['buildtype'] in ('0', '5'):
            if not mat.gl_roof:
                crit = [['Percent', 80, 'DF', 2, '1'], ['Ratio', 100, 'Uni', 0.4, '0.5'], ['Min', 100, 'PDF', 0.8, '0.5'], ['Percent', 80, 'Skyview', 1, '0.75']]
                ecrit = [['Percent', 80, 'DF', 4, '1'], ['Min', 100, 'PDF', 1.6, '0.75']] if simnode['coptions']['storey'] == '0' else [['Percent', 80, 'DF', 3, '1'], ['Min', 100, 'PDF', 1.2, '0.75']] 
            else:
                crit = [['Percent', 80, 'DF', 2, '1'], ['Ratio', 100, 'Uni', 0.7, '0.5'], ['Min', 100, 'PDF', 1.4, '0.5'], ['Percent', 100, 'Skyview', 1, '0.75']]
                ecrit = [['Percent', 80, 'DF', 4, '1'], ['Min', 100, 'PDF', 2.8, '0.75']] if simnode['coptions']['storey'] == '0' else [['Percent', 80, 'DF', 3, '1'], ['Min', 100, 'PDF', 2.1, '0.75']]
            spacetype = 'School' if simnode['coptions']['buildtype'] == '0' else 'Office & Other'
        elif simnode['coptions']['buildtype'] == '1':
            if not mat.gl_roof:
                crit = [['Percent', 80, 'DF', 2, '1'], ['Ratio', 100, 'Uni', 0.4, '0.5'], ['Min', 100, 'PDF', 0.8, '0.5'], ['Percent', 80, 'Skyview', 1, '0.75']]
                ecrit = [['Percent', 80, 'DF', 4, '1'], ['Min', 100, 'PDF', 1.6, '0.75']] if simnode['coptions']['storey'] == '0' else [['Percent', 80, 'DF', 3, '1'], ['Min', 100, 'PDF', 1.2, '0.75']]
            else:
                crit = [['Percent', 80, 'DF', 2, '1'], ['Ratio', 100, 'Uni', 0.7, '0.5'], ['Min', 100, 'PDF', 1.4, '0.5'], ['Percent', 100, 'Skyview', 1, '0.75']]
                ecrit= [['Percent', 80, 'DF', 4, '1'], ['Min', 100, 'PDF', 2.8, '0.75']] if simnode['coptions']['storey'] == '0' else [['Percent', 80, 'DF', 3, '1'], ['Min', 100, 'PDF', 2.1, '0.75']]
            spacetype = 'Higher Education'
        elif simnode['coptions']['buildtype'] == '2':
            crit = [['Percent', 80, 'DF', 2, '1']] if mat.hspacemenu == '0' else [['Percent', 80, 'DF', 3, '2']]
            ecrit = [['Percent', 80, 'DF', 4, '1'], ['Min', 100, 'PDF', 1.6, '0.75']] if simnode['coptions']['storey'] == '0' else [['Min', 100, 'PDF', 1.6, '0.75'], ['Min', 100, 'PDF', 1.2, '0.75']]
            spacetype = 'Healthcare - Patient' if mat.hspacemenu == '0' else 'Healthcare - Public'
        elif simnode['coptions']['buildtype'] == '3':
            if mat.brspacemenu == '0':
                crit = [['Percent', 80, 'DF', 2, '1'], ['Percent', 100, 'Skyview', 1, '0.75']]
                ecrit = [['Percent', 80, 'DF', 4, '1'], ['Min', 100, 'PDF', 1.6, '0.75']] if simnode['coptions']['storey'] == '0' else [['Percent', 80, 'DF', 3, '1'], ['Min', 100, 'PDF', 1.2, '0.75']]
                spacetype = 'Residential - Kitchen'
            elif mat.brspacemenu == '1':
                crit = [['Percent', 80, 'DF', 1.5, '1'], ['Percent', 100, 'Skyview', 1, '0.75']]
                ecrit = [['Percent', 80, 'DF', 4, '1'], ['Min', 100, 'PDF', 1.6, '0.75']] if simnode['coptions']['storey'] == '0' else [['Percent', 80, 'DF', 3, '1'], ['Min', 100, 'PDF', 1.2, '0.75']]
                spacetype = 'Residential - Living/Dining/Study'
            elif mat.brspacemenu == '2':
                if not mat.gl_roof:
                    crit = [['Percent', 80, 'DF', 2, '1'], ['Ratio', 100, 'Uni', 0.4, '0.5'], ['Min', 100, 'PDF', 0.8, '0.5'], ['Percent', 80, 'Skyview', 1, '0.75']]
                    ecrit = [['Percent', 80, 'DF', 4, '1'], ['Min', 100, 'PDF', 1.6, '0.75']] if simnode['coptions']['storey'] == '0' else [['Percent', 80, 'DF', 3, '1'], ['Min', 100, 'PDF', 1.2, '0.75']]
                else:
                    crit = [['Percent', 80, 'DF', 2, '1'], ['Ratio', 100, 'Uni', 0.7, '0.5'],['Min', 100, 'PDF', 1.4, '0.5'], ['Percent', 100, 'Skyview', 1, '0.75']] 
                    ecrit = [['Percent', 80, 'DF', 4, '1'], ['Min', 100, 'PDF', 2.8, '0.75']] if simnode['coptions']['storey'] == '0' else [['Percent', 80, 'DF', 3, '1'], ['Min', 100, 'PDF', 2.1, '0.75']]
                spacetype = 'Residential - Communal'
        elif simnode['coptions']['buildtype'] == '4':
            if mat.respacemenu == '0':
                crit = [['Percent', 35, 'PDF', 2, '1']]
                ecrit = [['Percent', 50, 'PDF', 2, '1']]
                spacetype = 'Retail - Sales'
            elif mat.respacemenu == '1':
                if not mat.gl_roof:
                    crit = [['Percent', 80, 'DF', 2, '1'], ['Ratio', 100, 'Uni', 0.4, '0.5'], ['Min', 100, 'PDF', 0.8, '0.5'], ['Percent', 80, 'Skyview', 1, '0.75']] 
                    ecrit = [['Percent', 80, 'DF', 4, '1'], ['Min', 100, 'PDF', 1.6, '0.75']] if simnode['coptions']['storey'] == '0' else [['Percent', 80, 'DF', 3, '1'], ['Min', 100, 'PDF', 1.2, '0.75']]   
                else:
                    crit = [['Percent', 80, 'DF', 2, '1'], ['Ratio', 100, 'Uni', 0.7, '0.5'], ['Min', 100, 'PDF', 1.4, '0.5'], ['Percent', 100, 'Skyview', 1, '0.75']]
                    ecrit = [['Percent', 80, 'DF', 4, '1'], ['Min', 100, 'PDF', 2.8, '0.75']] if simnode['coptions']['storey'] == '0' else [['Percent', 80, 'DF', 3, '1'],['Min', 100, 'PDF', 2.1, '0.75']] 
                spacetype = 'Retail - Occupied'
    
    elif simnode['coptions']['canalysis'] == '1':
        crit = [['Average', 100, 'DF', 2, '1'], ['Percent', 80, 'Skyview', 1, '0.75']] if mat.crspacemenu == '0' else [['Average', 100, 'DF', 1.5, '1'], ['Percent', 80, 'Skyview', 1, '0.75']]
        spacetype = 'Residential - Kitchen' if mat.crspacemenu == '0' else 'Residential - Living/Dining/Study'

    elif simnode['coptions']['canalysis'] == '2':
        if simnode['coptions']['buildtype'] == '0':
            crit = [['Percent', 30, 'DF', 2, '1'], ['Percent', 60, 'DF', 2, '1'], ['Percent', 90, 'DF', 2, '1'], ['Percent', 50, 'DF', 4, '1']]
            spacetype = 'School'
        if simnode['coptions']['buildtype'] == '1':
            crit = [['Percent', 30, 'DF', 2, '1'], ['Percent', 60, 'DF', 2, '1'], ['Percent', 90, 'DF', 2, '1']]
            spacetype = 'Higher Education'
        if simnode['coptions']['buildtype'] == '2':
            crit = [['Percent', 30, 'DF', 2.5, '1'], ['Percent', 60, 'DF', 2.5, '1'], ['Percent', 90, 'DF', 2.5, '1']] if mat.hspacemenu == '0' else [['Percent', 30, 'DF', 3, '1'], ['Percent', 60, 'DF', 3, '1'], ['Percent', 90, 'DF', 3, '1']]
            spacetype = 'Healthcare'
        if simnode['coptions']['buildtype'] == '3':
            crit = [['Percent', 60, 'DF', 2.0, '1'], ['Percent', 90, 'DF', 2.0, '1']] if mat.brspacemenu == '0' else [['Percent', 60, 'DF', 1.5, '1'], ['Percent', 90, 'DF', 1.5, '1']]   
            spacetype = 'Residential'             
        if simnode['coptions']['buildtype'] in ('4', '5'):
            crit = [['Percent', 30, 'DF', 2, '1'], ['Percent', 60, 'DF', 2, '1'], ['Percent', 90, 'DF', 2, '1']]
            spacetype = 'Retail/Office/Public' 
            
    elif simnode['coptions']['canalysis'] == '3':
        spacetype = ('Office/Education/Commercial', 'Healthcare')[int(simnode['coptions']['buildtype'])]
        if simnode['coptions']['buildtype'] == '0':
            crit = [['Percent', 55, 'SDA', 300, '2'], ['Percent', 75, 'SDA', 300, '1']]
        else:
            crit = [['Percent', 75, 'SDA', 300, '1'], ['Percent', 90, 'SDA', 300, '1']]
#            spacetype = 'Healthcare'
        crit.append(['Percent', 10, 'ASE', 1000, '1', 250])
                   
    return [[c[0], str(c[1]), c[2], str(c[3]), c[4]] for c in crit[:]], [[c[0], str(c[1]), c[2], str(c[3]), c[4]] for c in ecrit[:]], spacetype
    
def lividisplay(self, scene): 
    frames = range(scene['liparams']['fs'], scene['liparams']['fe'] + 1)
    
    if len(frames) > 1:
        if not self.data.animation_data:
            self.data.animation_data_create()
        
        self.data.animation_data.action = bpy.data.actions.new(name="LiVi {} MI".format(self.name))
        fis = [str(face.index) for face in self.data.polygons]
        lms = {fi: self.data.animation_data.action.fcurves.new(data_path='polygons[{}].material_index'.format(fi)) for fi in fis}
        for fi in fis:
            lms[fi].keyframe_points.add(len(frames))

    for f, frame in enumerate(frames):  
        bm = bmesh.new()
        bm.from_mesh(self.data)
        geom = bm.verts if scene['liparams']['cp'] == '1' else bm.faces  
        livires = geom.layers.float['{}{}'.format(unitdict[scene['liparams']['unit']], frame)]
        res = geom.layers.float['res{}'.format(frame)]
        oreslist = [g[livires] for g in geom]
        self['omax'][str(frame)], self['omin'][str(frame)], self['oave'][str(frame)] = max(oreslist), min(oreslist), sum(oreslist)/len(oreslist)
        smaxres, sminres =  max(scene['liparams']['maxres'].values()), min(scene['liparams']['minres'].values())
        if smaxres > sminres:        
            vals = (array([f[livires] for f in bm.faces]) - sminres)/(smaxres - sminres) if scene['liparams']['cp'] == '0' else \
                (array([(sum([vert[livires] for vert in f.verts])/len(f.verts)) for f in bm.faces]) - sminres)/(smaxres - sminres)
        else:
            vals = array([max(scene['liparams']['maxres'].values()) for x in range(len(bm.faces))])
    
        if livires != res:
            for g in geom:
                g[res] = g[livires]  
        if scene['liparams']['unit'] == 'Sky View':
            nmatis = [(0, 19)[v == 1] for v in vals]
        else:
            bins = array([0.05 * i for i in range(21)])
            nmatis = clip(digitize(vals, bins, right = True) - 1, 0, 19, out=None)
        bm.to_mesh(self.data)
        bm.free()
        if len(frames) == 1:
            self.data.polygons.foreach_set('material_index', nmatis)
        elif len(frames) > 1:
            for fii, fi in enumerate(fis):
                lms[fi].keyframe_points[f].co = frame, nmatis[fii]  
                
def retvpvloc(context):
    return bpy_extras.view3d_utils.region_2d_to_origin_3d(context.region, context.space_data.region_3d, (context.region.width/2.0, context.region.height/2.0))
          
def fvmat(self, mn, bound):
#    fvname = on.replace(" ", "_") + self.name.replace(" ", "_") 
    begin = '\n  {}\n  {{\n    type    '.format(mn)  
    end = ';\n  }\n'
    
    if bound == 'p':
        val = 'uniform {}'.format(self.flovi_b_sval) if not self.flovi_p_field else '$internalField'
        pdict = {'0': self.flovi_bmwp_type, '1': self.flovi_bmip_type, '2': self.flovi_bmop_type, '3': 'symmetryPlane', '4': 'empty'}
        ptdict = {'zeroGradient': 'zeroGradient', 'fixedValue': 'fixedValue;\n    value    {}'.format(val), 'calculated': 'calculated;\n    value    $internalField', 
        'freestreamPressure': 'freestreamPressure', 'symmetryPlane': 'symmetryPlane', 'empty': 'empty'}
#        if pdict[self.flovi_bmb_type] == 'zeroGradient':
        entry = ptdict[pdict[self.flovi_bmb_type]]            
#        return begin + entry + end 
    
    elif bound == 'U':
        val = 'uniform ({} {} {})'.format(*self.flovi_b_vval) if not self.flovi_u_field else '$internalField'
        Udict = {'0': self.flovi_bmwu_type, '1': self.flovi_bmiu_type, '2': self.flovi_bmou_type, '3': 'symmetryPlane', '4': 'empty'}
        Utdict = {'fixedValue': 'fixedValue;\n    value    {}'.format(val), 'slip': 'slip', 'inletOutlet': 'inletOutlet;\n    inletValue    $internalField\n    value    $internalField',
                  'pressureInletOutletVelocity': 'pressureInletOutletVelocity;\n    value    $internalField', 'zeroGradient': 'zeroGradient', 'symmetryPlane': 'symmetryPlane', 
                  'freestream': 'freestream;\n    freestreamValue    $internalField','calculated': 'calculated;\n    value    $internalField', 'empty': 'empty'}
        entry = Utdict[Udict[self.flovi_bmb_type]]            
#        return begin + entry + end
        
    elif bound == 'nut':
        ndict = {'0': self.flovi_bmwnut_type, '1': self.flovi_bminut_type, '2': self.flovi_bmonut_type, '3': 'symmetryPlane', '4': 'empty'}
        ntdict = {'nutkWallFunction': 'nutkWallFunction;\n    value    $internalField', 'nutUSpaldingWallFunction': 'nutUSpaldingWallFunction;\n    value    $internalField', 
        'calculated': 'calculated;\n    value    $internalField', 'inletOutlet': 'inletOutlet;\n    inletValue    $internalField\n    value    $internalField',  'symmetryPlane': 'symmetryPlane','empty': 'empty'}
        entry = ntdict[ndict[self.flovi_bmb_type]]            
#        return begin + entry + end

    elif bound == 'k':
        kdict = {'0': self.flovi_bmwk_type, '1': self.flovi_bmik_type, '2': self.flovi_bmok_type, '3': 'symmetryPlane', '4': 'empty'}
        ktdict = {'fixedValue': 'fixedValue;\n    value    $internalField', 'kqRWallFunction': 'kqRWallFunction;\n    value    $internalField', 'inletOutlet': 'inletOutlet;\n    inletValue    $internalField\n    value    $internalField',
        'calculated': 'calculated;\n    value    $internalField', 'symmetryPlane': 'symmetryPlane', 'empty': 'empty'}
        entry = ktdict[kdict[self.flovi_bmb_type]]            
#        return begin + entry + end
        
    elif bound == 'e':
        edict = {'0': self.flovi_bmwe_type, '1': self.flovi_bmie_type, '2': self.flovi_bmoe_type, '3': 'symmetryPlane', '4': 'empty'}
        etdict = {'symmetryPlane': 'symmetryPlane', 'empty': 'empty', 'inletOutlet': 'inletOutlet;\n    inletValue    $internalField\n    value    $internalField', 'fixedValue': 'fixedValue;\n    value    $internalField', 
                  'epsilonWallFunction': 'epsilonWallFunction;\n    value    $internalField', 'calculated': 'calculated;\n    value    $internalField', 'symmetryPlane': 'symmetryPlane', 'empty': 'empty'}
        entry = etdict[edict[self.flovi_bmb_type]]            
#        return begin + entry + end
        
    elif bound == 'o':
        odict = {'0': self.flovi_bmwo_type, '1': self.flovi_bmio_type, '2': self.flovi_bmoo_type, '3': 'symmetryPlane', '4': 'empty'}
        otdict = {'symmetryPlane': 'symmetryPlane', 'empty': 'empty', 'inletOutlet': 'inletOutlet;\n    inletValue    $internalField\n    value    $internalField', 'zeroGradient': 'zeroGradient', 
                  'omegaWallFunction': 'omegaWallFunction;\n    value    $internalField', 'fixedValue': 'fixedValue;\n    value    $internalField'}
        entry = otdict[odict[self.flovi_bmb_type]]            
#        return begin + entry + end
        
    elif bound == 'nutilda':
        ntdict = {'0': self.flovi_bmwnutilda_type, '1': self.flovi_bminutilda_type, '2': self.flovi_bmonutilda_type, '3': 'symmetryPlane', '4': 'empty'}
        nttdict = {'fixedValue': 'fixedValue;\n    value    $internalField', 'inletOutlet': 'inletOutlet;\n    inletValue    $internalField\n    value    $internalField', 'empty': 'empty', 
                   'zeroGradient': 'zeroGradient', 'freestream': 'freestream\n    freeStreamValue  $internalField\n', 'symmetryPlane': 'symmetryPlane'} 
        entry = nttdict[ntdict[self.flovi_bmb_type]]            
    return begin + entry + end
        
            
def radpoints(o, faces, sks):
    fentries = ['']*len(faces) 
    mns = [m.name.replace(" ", "_") for m in o.data.materials]
#    mrms = [m.radmatmenu for m in o.data.materials]
    on = o.name.replace(" ", "_")
    if sks:
        (skv0, skv1, skl0, skl1) = sks
    for f, face in enumerate(faces):
        fmi = face.material_index
#        fmat = o.data.materials[face.material_index]
#        mname = '{}_{}_{}'.format(mns[fmi], on, face.index) if mrms[fmi] == '8' else mns[fmi]
        mname = mns[fmi]
        fentry = "# Polygon \n{} polygon poly_{}_{}\n0\n0\n{}\n".format(mname, on, face.index, 3*len(face.verts))
        if sks:
            ventries = ''.join([" {0[0]:.4f} {0[1]:.4f} {0[2]:.4f}\n".format((o.matrix_world*mathutils.Vector((v[skl0][0]+(v[skl1][0]-v[skl0][0])*skv1, v[skl0][1]+(v[skl1][1]-v[skl0][1])*skv1, v[skl0][2]+(v[skl1][2]-v[skl0][2])*skv1)))) for v in face.verts])
        else:
            ventries = ''.join([" {0[0]:.4f} {0[1]:.4f} {0[2]:.4f}\n".format(v.co) for v in face.verts])
        fentries[f] = ''.join((fentry, ventries+'\n'))        
    return ''.join(fentries)
                       
def viparams(op, scene):
    bdfp = bpy.data.filepath
    if not bdfp:
        op.report({'ERROR'},"The Blender file has not been saved. Save the Blender file before exporting")
        return 'Save file'
    if " "  in bdfp:
        op.report({'ERROR'},"The directory path or Blender filename has a space in it. Please save again without any spaces in the file name or the directory path")
        return 'Rename file'

    isascii = lambda s: len(s) == len(s.encode())
    if not isascii(bdfp):
        op.report({'WARNING'},"The directory path or Blender filename has non-ascii characters in it. Photon mapping may not work")
    
    fd, fn = os.path.dirname(bpy.data.filepath), os.path.splitext(os.path.basename(bpy.data.filepath))[0]
    if not os.path.isdir(os.path.join(fd, fn)):
        os.makedirs(os.path.join(fd, fn))
    if not os.path.isdir(os.path.join(fd, fn, 'obj')):
        os.makedirs(os.path.join(fd, fn, 'obj'))
    if not os.path.isdir(os.path.join(fd, fn, 'bsdfs')):
        os.makedirs(os.path.join(fd, fn, 'bsdfs'))
    if not os.path.isdir(os.path.join(fd, fn, 'images')):
        os.makedirs(os.path.join(fd, fn, 'images'))
    if not os.path.isdir(os.path.join(fd, fn, 'lights')):
        os.makedirs(os.path.join(fd, fn, 'lights'))
    if not os.path.isdir(os.path.join(fd, fn, 'textures')):
        os.makedirs(os.path.join(fd, fn, 'textures'))
    if not os.path.isdir(os.path.join(fd, fn, 'Openfoam')):
        os.makedirs(os.path.join(fd, fn, 'Openfoam'))
    if not os.path.isdir(os.path.join(fd, fn, 'Openfoam', 'system')):
        os.makedirs(os.path.join(fd, fn, 'Openfoam', "system"))
    if not os.path.isdir(os.path.join(fd, fn, 'Openfoam', 'constant')):
        os.makedirs(os.path.join(fd, fn, 'Openfoam', "constant"))
    if not os.path.isdir(os.path.join(fd, fn, 'Openfoam', 'constant', 'polyMesh')):
        os.makedirs(os.path.join(fd, fn, 'Openfoam', "constant", "polyMesh"))
    if not os.path.isdir(os.path.join(fd, fn, 'Openfoam', 'constant', 'triSurface')):
        os.makedirs(os.path.join(fd, fn, 'Openfoam', "constant", "triSurface"))
    if not os.path.isdir(os.path.join(fd, fn, 'Openfoam', '0')):
        os.makedirs(os.path.join(fd, fn, 'Openfoam', "0"))
        
    nd = os.path.join(fd, fn)
    fb, ofb, lfb, tfb, offb, idf  = os.path.join(nd, fn), os.path.join(nd, 'obj'), os.path.join(nd, 'lights'), os.path.join(nd, 'textures'), os.path.join(nd, 'Openfoam'), os.path.join(nd, 'in.idf')
    offzero, offs, offc, offcp, offcts = os.path.join(offb, '0'), os.path.join(offb, 'system'), os.path.join(offb, 'constant'), os.path.join(offb, 'constant', "polyMesh"), os.path.join(offb, 'constant', "triSurface")
    if not scene.get('viparams'):
        scene['viparams'] = {}
    scene['viparams']['cat'] = ('cat ', 'type ')[str(sys.platform) == 'win32']
    scene['viparams']['nproc'] = str(multiprocessing.cpu_count())
    scene['viparams']['wnproc'] = str(multiprocessing.cpu_count()) if str(sys.platform) != 'win32' else '1'
    scene['viparams']['filepath'] = bpy.data.filepath
    scene['viparams']['filename'] = fn
    scene['viparams']['filedir'] = fd
    scene['viparams']['newdir'] = nd 
    scene['viparams']['filebase'] = fb
    if not scene.get('liparams'):
        scene['liparams'] = {}
    scene['liparams']['objfilebase'] = ofb
    scene['liparams']['lightfilebase'] = lfb
    scene['liparams']['texfilebase'] = tfb
    scene['liparams']['disp_count'] = 0
    if not scene.get('enparams'):
        scene['enparams'] = {}
    scene['enparams']['idf_file'] = idf
    scene['enparams']['epversion'] = '8.6'
    if not scene.get('flparams'):
        scene['flparams'] = {}
    scene['flparams']['offilebase'] = offb
    scene['flparams']['ofsfilebase'] = offs
    scene['flparams']['ofcfilebase'] = offc
    scene['flparams']['ofcpfilebase'] = offcp
    scene['flparams']['of0filebase'] = offzero
    scene['flparams']['ofctsfilebase'] = offcts
        
def nodestate(self, opstate):
    if self['exportstate'] !=  opstate:
        self.exported = False
        if self.bl_label[0] != '*':
            self.bl_label = '*'+self.bl_label
    else:
        self.exported = True
        if self.bl_label[0] == '*':
            self.bl_label = self.bl_label[1:-1]

def face_centre(ob, obresnum, f):
    if obresnum:
        vsum = mathutils.Vector((0, 0, 0))
        for v in f.vertices:
            vsum = ob.active_shape_key.data[v].co + vsum
        return(vsum/len(f.vertices))
    else:
        return(f.center)

def v_pos(ob, v):
    return(ob.active_shape_key.data[v].co if ob.lires else ob.data.vertices[v].co)
    
def newrow(layout, s1, root, s2):
    row = layout.row()
    row.label(s1)
    row.prop(root, s2)
    
def newrow2(row, s1, root, s2):
    row.label(s1)
    row.prop(root, s2)

def retobj(name, fr, node, scene):
    if node.animmenu == "Geometry":
        return(os.path.join(scene['liparams']['objfilebase'], "{}-{}.obj".format(name.replace(" ", "_"), fr)))
    else:
        return(os.path.join(scene['liparams']['objfilebase'], "{}-{}.obj".format(name.replace(" ", "_"), bpy.context.scene.frame_start)))

def retelaarea(node):
    inlinks = [sock.links[0] for sock in node.inputs if sock.bl_idname in ('EnViSSFlowSocket', 'EnViSFlowSocket') and sock.links]
    outlinks = [sock.links[:] for sock in node.outputs if sock.bl_idname in ('EnViSSFlowSocket', 'EnViSFlowSocket') and sock.links]
    inosocks = [link.from_socket for link in inlinks if inlinks and link.from_socket.node.get('zone') and link.from_socket.node.zone in [o.name for o in bpy.data.objects]]
    outosocks = [link.to_socket for x in outlinks for link in x if link.to_socket.node.get('zone') and link.to_socket.node.zone in [o.name for o in bpy.data.objects]]
    if outosocks or inosocks:
        elaarea = max([facearea(bpy.data.objects[sock.node.zone], bpy.data.objects[sock.node.zone].data.polygons[int(sock.sn)]) for sock in outosocks + inosocks])
        node["_RNA_UI"] = {"ela": {"max":elaarea, "min": 0.0001}}
        
def objmode():
    if bpy.context.active_object and bpy.context.active_object.type == 'MESH' and not bpy.context.active_object.hide:
        bpy.ops.object.mode_set(mode = 'OBJECT')

def objoin(obs):
    bpy.ops.object.select_all(action='DESELECT')
    for o in obs:
        o.select = True
    bpy.context.scene.objects.active = obs[-1]
    bpy.ops.object.join()
    return bpy.context.active_object
    
def retmesh(name, fr, node, scene):
    if node.animmenu in ("Geometry", "Material"):
        return(os.path.join(scene['liparams']['objfilebase'], '{}-{}.mesh'.format(name.replace(" ", "_"), fr)))
    else:
        return(os.path.join(scene['liparams']['objfilebase'], '{}-{}.mesh'.format(name.replace(" ", "_"), bpy.context.scene.frame_start)))

def nodeinputs(node):
    try:
        ins = [i for i in node.inputs if not i.hide]
        if ins and not all([i.links for i in ins]):
            return 0
        elif ins and any([i.links[0].from_node.use_custom_color for i in ins if i.links]):
            return 0
        else:
            inodes = [i.links[0].from_node for i in ins if i.links[0].from_node.inputs]
            for inode in inodes:
                iins = [i for i in inode.inputs if not i.hide]
                if iins and not all([i.is_linked for i in iins]):
                    return 0
                elif iins and not all([i.links[0].from_node.use_custom_color for i in iins if i.is_linked]):
                    return 0
        return 1
    except:
        pass

def retmat(fr, node, scene):
    if node.animmenu == "Material":
        return("{}-{}.rad".format(scene['viparams']['filebase'], fr))
    else:
        return("{}-{}.rad".format(scene['viparams']['filebase'], scene.frame_start))

def retsky(fr, node, scene):
    if node.animmenu == "Time":
        return("{}-{}.sky".format(scene['viparams']['filebase'], fr))
    else:
        return("{}-{}.sky".format(scene['viparams']['filebase'], scene.frame_start))

def nodeexported(self):
    self.exported = 0

def negneg(x):
    x = 0 if float(x) < 0 else x        
    return float(x)

def clearanim(scene, obs):
    for o in obs:
        selobj(scene, o)
        o.animation_data_clear()
        o.data.animation_data_clear()        
        while o.data.shape_keys:
            bpy.context.object.active_shape_key_index = 0
            bpy.ops.object.shape_key_remove(all=True)
            
def clearfiles(filebase):
    fileList = os.listdir(filebase)
    for fileName in fileList:
        os.remove(os.path.join(filebase, fileName))
                    
def clearscene(scene, op):
    for ob in [ob for ob in scene.objects if ob.type == 'MESH' and ob.layers[scene.active_layer]]:
        if ob.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode = 'OBJECT')
        if ob.get('lires'):
            scene.objects.unlink(ob)       
        if scene.get('livig') and ob.name in scene['livig']:
            v, f, svv, svf = [0] * 4             
            if 'export' in op.name or 'simulation' in op.name:
                bm = bmesh.new()
                bm.from_mesh(ob.data)
#                if "export" in op.name:
#                    if bm.faces.layers.int.get('rtindex'):
#                        bm.faces.layers.int.remove(bm.faces.layers.int['rtindex'])
#                    if bm.verts.layers.int.get('rtindex'):
#                        bm.verts.layers.int.remove(bm.verts.layers.int['rtindex'])
                if "simulation" in op.name:
                    while bm.verts.layers.float.get('res{}'.format(v)):
                        livires = bm.verts.layers.float['res{}'.format(v)]
                        bm.verts.layers.float.remove(livires)
                        v += 1
                    while bm.faces.layers.float.get('res{}'.format(f)):
                        livires = bm.faces.layers.float['res{}'.format(f)]
                        bm.faces.layers.float.remove(livires)
                        f += 1
                bm.to_mesh(ob.data)
                bm.free()

    for mesh in bpy.data.meshes:
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)

    for lamp in bpy.data.lamps:
        if lamp.users == 0:
            bpy.data.lamps.remove(lamp)

    for oldgeo in bpy.data.objects:
        if oldgeo.users == 0:
            bpy.data.objects.remove(oldgeo)

    for sk in bpy.data.shape_keys:
        if sk.users == 0:
            for keys in sk.keys():
                keys.animation_data_clear()

#def zrupdate(zonemenu, innode):
#    rl = innode['reslists']
#    for r in rl:
#        print(dir(zonemenu), r[2])
#    zri = [(zr[3], zr[3], 'Plot {}'.format(zr[3])) for zr in rl if zr[2] == zonemenu]
#    print(zri)
#    return zri
#    del self.zonermenu
#    zonermenu = bpy.props.EnumProperty(items = zri, name = '', description = '', default = zri[0][0])
#    self.zonermenu = zonermenu
#    self.items = 
        
def rtupdate(self, context):
    try: 
        rl = self.links[0].from_node['reslists']
        zri = set([(zr[1], zr[1], 'Plot {}'.format(zr[1])) for zr in rl if zr[0] == self.framemenu])
        return zri
    except:
        return []
               
def iprop(iname, idesc, imin, imax, idef):
    return(IntProperty(name = iname, description = idesc, min = imin, max = imax, default = idef))
def eprop(eitems, ename, edesc, edef):
    return(EnumProperty(items=eitems, name = ename, description = edesc, default = edef))
def bprop(bname, bdesc, bdef):
    return(BoolProperty(name = bname, description = bdesc, default = bdef))
def sprop(sname, sdesc, smaxlen, sdef):
    return(StringProperty(name = sname, description = sdesc, maxlen = smaxlen, default = sdef))
def fprop(fname, fdesc, fmin, fmax, fdef):
    return(FloatProperty(name = fname, description = fdesc, min = fmin, max = fmax, default = fdef))
def fvprop(fvsize, fvname, fvattr, fvdef, fvsub, fvmin, fvmax):
    return(FloatVectorProperty(size = fvsize, name = fvname, attr = fvattr, default = fvdef, subtype =fvsub, min = fvmin, max = fvmax))
def niprop(iname, idesc, imin, imax, idef):
        return(IntProperty(name = iname, description = idesc, min = imin, max = imax, default = idef, update = nodeexported))
def neprop(eitems, ename, edesc, edef):
    return(EnumProperty(items=eitems, name = ename, description = edesc, default = edef, update = nodeexported))
def nbprop(bname, bdesc, bdef):
    return(BoolProperty(name = bname, description = bdesc, default = bdef, update = nodeexported))
def nsprop(sname, sdesc, smaxlen, sdef):
    return(StringProperty(name = sname, description = sdesc, maxlen = smaxlen, default = sdef, update = nodeexported))
def nfprop(fname, fdesc, fmin, fmax, fdef):
    return(FloatProperty(name = fname, description = fdesc, min = fmin, max = fmax, default = fdef, update = nodeexported))
def nfvprop(fvname, fvattr, fvdef, fvsub):
    return(FloatVectorProperty(name=fvname, attr = fvattr, default = fvdef, subtype = fvsub, update = nodeexported))

def boundpoly(obj, mat, poly, enng):
    mat = obj.data.materials[poly.material_index]
    if mat.envi_boundary:
        nodes = [node for node in enng.nodes if hasattr(node, 'zone') and node.zone == obj.name]
        for node in nodes:
            insock = node.inputs['{}_{}_b'.format(mat.name, poly.index)]
            outsock = node.outputs['{}_{}_b'.format(mat.name, poly.index)]              
            if insock.links:
                bobj = bpy.data.objects[insock.links[0].from_node.zone]
                bpoly = bobj.data.polygons[int(insock.links[0].from_socket.name.split('_')[-2])]
#                if bobj.data.materials[bpoly.material_index] == mat:# and max(bpolyloc - polyloc) < 0.001 and abs(bpoly.area - poly.area) < 0.01:
                return(("Surface", node.inputs['{}_{}_b'.format(mat.name, poly.index)].links[0].from_node.zone+'_'+str(bpoly.index), "NoSun", "NoWind"))
        
            elif outsock.links:
                bobj = bpy.data.objects[outsock.links[0].to_node.zone]
                bpoly = bobj.data.polygons[int(outsock.links[0].to_socket.name.split('_')[-2])]
#                if bobj.data.materials[bpoly.material_index] == mat:# and max(bpolyloc - polyloc) < 0.001 and abs(bpoly.area - poly.area) < 0.01:
                return(("Surface", node.outputs['{}_{}_b'.format(mat.name, poly.index)].links[0].to_node.zone+'_'+str(bpoly.index), "NoSun", "NoWind"))
            else:
                return(("Adiabatic", "", "NoSun", "NoWind"))

    elif mat.envi_thermalmass:
        return(("Adiabatic", "", "NoSun", "NoWind"))
    elif poly.calc_center_bounds()[2] <= 0:
        return(("Ground", '{}_{}'.format(obj.name, poly.index), "NoSun", "NoWind"))
    else:
        return(("Outdoors", "", "SunExposed", "WindExposed"))

def objvol(op, obj):
    bm , floor, roof, mesh = bmesh.new(), [], [], obj.data
    bm.from_object(obj, bpy.context.scene)
    for f in mesh.polygons:
        if obj.data.materials[f.material_index].envi_con_type == 'Floor':
            floor.append((facearea(obj, f), (obj.matrix_world*mathutils.Vector(f.center))[2]))
        elif obj.data.materials[f.material_index].envi_con_type == 'Roof':
            roof.append((facearea(obj, f), (obj.matrix_world*mathutils.Vector(f.center))[2]))
    zfloor = list(zip(*floor))
    if not zfloor and op:
        op.report({'INFO'},"Zone has no floor area")

    return(bm.calc_volume()*obj.scale[0]*obj.scale[1]*obj.scale[2])

def ceilheight(obj, vertz):
    mesh = obj.data
    for vert in mesh.vertices:
        vertz.append((obj.matrix_world * vert.co)[2])
    zmax, zmin = max(vertz), min(vertz)
    ceiling = [max((obj.matrix_world * mesh.vertices[poly.vertices[0]].co)[2], (obj.matrix_world * mesh.vertices[poly.vertices[1]].co)[2], (obj.matrix_world * mesh.vertices[poly.vertices[2]].co)[2]) for poly in mesh.polygons if max((obj.matrix_world * mesh.vertices[poly.vertices[0]].co)[2], (obj.matrix_world * mesh.vertices[poly.vertices[1]].co)[2], (obj.matrix_world * mesh.vertices[poly.vertices[2]].co)[2]) > 0.9 * zmax]
    floor = [min((obj.matrix_world * mesh.vertices[poly.vertices[0]].co)[2], (obj.matrix_world * mesh.vertices[poly.vertices[1]].co)[2], (obj.matrix_world * mesh.vertices[poly.vertices[2]].co)[2]) for poly in mesh.polygons if min((obj.matrix_world * mesh.vertices[poly.vertices[0]].co)[2], (obj.matrix_world * mesh.vertices[poly.vertices[1]].co)[2], (obj.matrix_world * mesh.vertices[poly.vertices[2]].co)[2]) < zmin + 0.1 * (zmax - zmin)]
    return(sum(ceiling)/len(ceiling)-sum(floor)/len(floor))

def vertarea(mesh, vert):
    area = 0
    faces = [face for face in vert.link_faces] 
    if hasattr(mesh.verts, "ensure_lookup_table"):
        mesh.verts.ensure_lookup_table()
    if len(faces) > 1:
        for f, face in enumerate(faces):
            ovs, oes = [], []
            fvs = [le.verts[(0, 1)[le.verts[0] == vert]] for le in vert.link_edges]
            ofaces = [oface for oface in faces if len([v for v in oface.verts if v in face.verts]) == 2]    
            for oface in ofaces:
                oes.append([e for e in face.edges if e in oface.edges])
                
                ovs.append([i for i in face.verts if i in oface.verts])
            
            if len(ovs) == 1:                
                sedgevs = (vert.index, [v.index for v in fvs if v not in ovs][0])
                sedgemp = mathutils.Vector([((mesh.verts[sedgevs[0]].co)[i] + (mesh.verts[sedgevs[1]].co)[i])/2 for i in range(3)])
                eps = [mathutils.geometry.intersect_line_line(face.calc_center_median(), ofaces[0].calc_center_median(), ovs[0][0].co, ovs[0][1].co)[1]] + [sedgemp]
            elif len(ovs) == 2:
                eps = [mathutils.geometry.intersect_line_line(face.calc_center_median(), ofaces[i].calc_center_median(), ovs[i][0].co, ovs[i][1].co)[1] for i in range(2)]
            else:
               return 0
            area += mathutils.geometry.area_tri(vert.co, *eps) + mathutils.geometry.area_tri(face.calc_center_median(), *eps)
    elif len(faces) == 1:
        eps = [(ev.verts[0].co +ev.verts[1].co)/2 for ev in vert.link_edges]
        eangle = (vert.link_edges[0].verts[0].co - vert.link_edges[0].verts[1].co).angle(vert.link_edges[1].verts[0].co - vert.link_edges[1].verts[1].co)
        area = mathutils.geometry.area_tri(vert.co, *eps) + mathutils.geometry.area_tri(faces[0].calc_center_median(), *eps) * 2*pi/eangle
    return area       

def facearea(obj, face):
    omw = obj.matrix_world
    vs = [omw*mathutils.Vector(face.center)] + [omw*obj.data.vertices[v].co for v in face.vertices] + [omw*obj.data.vertices[face.vertices[0]].co]
    return(vsarea(obj, vs))

def vsarea(obj, vs):
    if len(vs) == 5:
        cross = mathutils.Vector.cross(vs[3]-vs[1], vs[3]-vs[2])
        return(0.5*(cross[0]**2 + cross[1]**2 +cross[2]**2)**0.5)
    else:
        i, area = 0, 0
        while i < len(vs) - 2:
            cross = mathutils.Vector.cross(vs[0]-vs[1+i], vs[0]-vs[2+i])
            area += 0.5*(cross[0]**2 + cross[1]**2 +cross[2]**2)**0.5
            i += 1
        return(area)

def wind_rose(maxws, wrsvg, wrtype):
    zp, scene = 0, bpy.context.scene    
    bm = bmesh.new()
    wrme = bpy.data.meshes.new("Wind_rose")   
    wro = bpy.data.objects.new('Wind_rose', wrme)     
    scene.objects.link(wro)
    scene.objects.active = wro
    wro.select, wro.location = True, (0, 0 ,0)    
    svg = minidom.parse(wrsvg)
    pos_strings = [path.getAttribute('d') for path in svg.getElementsByTagName('path')]
    style_strings = [path.getAttribute('style').split(';') for path in svg.getElementsByTagName('path')]     
    dimen = [eval(path.getAttribute('height').strip('pt')) for path in svg.getElementsByTagName('svg')][0]
    scale = 0.04 * dimen
    svg.unlink()    
    sposnew = [[(eval(ss.split()[ss.index('M') + 1]) - dimen/2) * 0.1, (eval(ss.split()[ss.index('M') + 2]) - dimen/2) * -0.1, 0.05] for ss in pos_strings]
    lposnew = [[[(eval(ss.split()[li + 1]) - dimen/2) * 0.1, (eval(ss.split()[li + 2]) - dimen/2) * -0.1, 0.05] for li in [si for si, s in enumerate(ss.split()) if s == 'L']] for ss in pos_strings]

    for stsi, sts in enumerate(style_strings):        
        if 'fill:#' in sts[0] and sts[0][-6:] != 'ffffff':
            hexcol, col = sts[0][-7:], sts[0][-6:]
            fillrgb = colors.hex2color(hexcol)

            if 'wr-{}'.format(col) not in [mat.name for mat in bpy.data.materials]:
                bpy.data.materials.new('wr-{}'.format(col))
            bpy.data.materials['wr-{}'.format(col)].diffuse_color = fillrgb

            if 'wr-{}'.format(col) not in [mat.name for mat in wro.data.materials]:
                bpy.ops.object.material_slot_add()
                wro.material_slots[-1].material = bpy.data.materials['wr-{}'.format(col)]    

            vs = [bm.verts.new(pos) for pos in [sposnew[stsi]] + lposnew[stsi]] 
            vs.reverse()                       

            if len(vs) > 2:
                nf = bm.faces.new(vs[::])
                nf.material_index = wro.data.materials[:].index(wro.data.materials['wr-{}'.format(col)])                            
                if wrtype in ('2', '3', '4'):
                    zp += 0.0005 * scale 
                    for vert in nf.verts:
                        vert.co[2] = zp
                        
    if 'wr-000000' not in [mat.name for mat in bpy.data.materials]:
        bpy.data.materials.new('wr-000000')
        bpy.data.materials['wr-000000'].diffuse_color = (0, 0, 0)
                                
    if 'wr-000000' not in [mat.name for mat in wro.data.materials]:
        bpy.ops.object.material_slot_add()
        wro.material_slots[-1].material = bpy.data.materials['wr-000000']        
            
    bmesh.ops.remove_doubles(bm, verts=vs, dist = scale * 0.01)    
            
    if wrtype in ('0', '1', '3', '4'):            
        thick = scale * 0.005 if wrtype == '4' else scale * 0.0005
        faces = bmesh.ops.inset_individual(bm, faces=bm.faces, thickness = thick, use_even_offset = True)['faces']
        if wrtype == '4':
            [bm.faces.remove(f) for f in bm.faces if f not in faces]
        else:
            for face in faces:
                face.material_index = wro.data.materials[:].index(wro.data.materials['wr-000000'])

    bm.to_mesh(wro.data)
    bm.free()
    
    bpy.ops.mesh.primitive_circle_add(vertices = 132, fill_type='NGON', radius=scale*1.2, view_align=False, enter_editmode=False, location=(0, 0, -0.01))
    wrbo = bpy.context.active_object
    if 'wr-base'not in [mat.name for mat in bpy.data.materials]:
        bpy.data.materials.new('wr-base')
        bpy.data.materials['wr-base'].diffuse_color = (1,1,1)
    bpy.ops.object.material_slot_add()
    wrbo.material_slots[-1].material = bpy.data.materials['wr-base']
    return (objoin((wrbo, wro)), scale)
    
def compass(loc, scale, wro, mat):
    txts = []
    come = bpy.data.meshes.new("Compass")   
    coo = bpy.data.objects.new('Compass', come)
    coo.location = loc
    bpy.context.scene.objects.link(coo)
    bpy.context.scene.objects.active = coo
    bpy.ops.object.material_slot_add()
    coo.material_slots[-1].material = mat
    bm = bmesh.new()
    matrot = Matrix.Rotation(pi*0.25, 4, 'Z')
    
    for i in range(1, 11):
        bmesh.ops.create_circle(bm, cap_ends=False, diameter=scale*((i**2)/10)*0.1, segments=132,  matrix=Matrix.Rotation(pi/64, 4, 'Z')*Matrix.Translation((0, 0, 0)))
    bmesh.ops.create_circle(bm, cap_ends=False, diameter=scale*1.075, segments=132,  matrix=Matrix.Rotation(pi/64, 4, 'Z')*Matrix.Translation((0, 0, 0)))
    bmesh.ops.create_circle(bm, cap_ends=False, diameter=scale*1.175, segments=132,  matrix=Matrix.Rotation(pi/64, 4, 'Z')*Matrix.Translation((0, 0, 0)))
    
    for edge in bm.edges:
        edge.select_set(False) if edge.index % 3 or edge.index > 1187 else edge.select_set(True)
    
    bmesh.ops.delete(bm, geom = [edge for edge in bm.edges if edge.select], context = 2)
    newgeo = bmesh.ops.extrude_edge_only(bm, edges = bm.edges, use_select_history=False)
    
    for v, vert in enumerate(newgeo['geom'][:1584]):
        vert.co = vert.co - (vert.co - coo.location).normalized() * scale * (0.0025, 0.005)[v > 1187]
        vert.co[2] = 0
           
    bmesh.ops.create_circle(bm, cap_ends=True, diameter=scale *0.005, segments=8, matrix=Matrix.Rotation(-pi/8, 4, 'Z')*Matrix.Translation((0, 0, 0)))
    matrot = Matrix.Rotation(pi*0.25, 4, 'Z')
    degmatrot = Matrix.Rotation(pi*0.125, 4, 'Z')
    tmatrot = Matrix.Rotation(0, 4, 'Z')
    direc = Vector((0, 1, 0))

    for i, edge in enumerate(bm.edges[-8:]):
        verts = bmesh.ops.extrude_edge_only(bm, edges = [edge], use_select_history=False)['geom'][:2]
        for vert in verts:
            vert.co += 1.0*scale*(tmatrot*direc)
            vert.co[2] = 0
        bpy.ops.object.text_add(view_align=False, enter_editmode=False, location=Vector(loc) + scale*1.13*(tmatrot*direc), rotation=tmatrot.to_euler())
        txt = bpy.context.active_object
        txt.scale, txt.data.body, txt.data.align_x, txt.data.align_y, txt.location[2]  = (scale*0.075, scale*0.075, scale*0.075), ('N', 'NW', 'W', 'SW', 'S', 'SE', 'E', 'NE')[i], 'CENTER', 'CENTER', txt.location[2]
        bpy.ops.object.convert(target='MESH')
        bpy.ops.object.material_slot_add()
        txt.material_slots[-1].material = mat
        txts.append(txt)
        tmatrot = tmatrot * matrot

    tmatrot = Matrix.Rotation(0, 4, 'Z')
    for d in range(16):
        bpy.ops.object.text_add(view_align=False, enter_editmode=False, location=Vector(loc) + scale*1.04*(tmatrot*direc), rotation=tmatrot.to_euler())
        txt = bpy.context.active_object
        txt.scale, txt.data.body, txt.data.align_x, txt.data.align_y, txt.location[2]  = (scale*0.05, scale*0.05, scale*0.05), (u'0\u00B0', u'337.5\u00B0', u'315\u00B0', u'292.5\u00B0', u'270\u00B0', u'247.5\u00B0', u'225\u00B0', u'202.5\u00B0', u'180\u00B0', u'157.5\u00B0', u'135\u00B0', u'112.5\u00B0', u'90\u00B0', u'67.5\u00B0', u'45\u00B0', u'22.5\u00B0')[d], 'CENTER', 'CENTER', txt.location[2]
        bpy.ops.object.convert(target='MESH')
        bpy.ops.object.material_slot_add()
        txt.material_slots[-1].material = mat
        txts.append(txt)
        tmatrot = tmatrot * degmatrot
    
    bm.to_mesh(come)
    bm.free()
    return objoin(txts + [coo] + [wro])

def spathrange(mats):
    sprme = bpy.data.meshes.new("SPRange")   
    spro = bpy.data.objects.new('SPRrange', sprme)
    bpy.context.scene.objects.link(spro)
    bpy.context.scene.objects.active = spro
    spro.location = (0, 0, 0)
    bm = bmesh.new()
    params = ((177, 0.05, 0), (80, 0.1, 1), (355, 0.15, 2)) if bpy.context.scene.latitude >= 0 else ((355, 0.05, 0), (80, 0.1, 1), (177, 0.15, 2))
    
    for param in params:
        bpy.ops.object.material_slot_add()
        spro.material_slots[-1].material = mats[param[2]]
        morn = solarRiseSet(param[0], 0, bpy.context.scene.latitude, bpy.context.scene.longitude, 'morn')
        eve = solarRiseSet(param[0], 0, bpy.context.scene.latitude, bpy.context.scene.longitude, 'eve')
        if morn or param[2] == 0:
            if morn:
                mornevediff = eve - morn if bpy.context.scene.latitude >= 0 else 360 - eve + morn
            else:
                mornevediff = 360# if bpy.context.scene.latitude >= 0 else 360
            
            startset = morn if bpy.context.scene.latitude >= 0 else eve
            angrange = [startset + a * 0.0125 * mornevediff for a in range (0, 81)]
            bm.verts.new().co = (95*sin(angrange[0]*pi/180), 95*cos(angrange[0]*pi/180), param[1])
        
            for a in angrange[1:-1]:
                bm.verts.new().co = (92*sin(a*pi/180), 92*cos(a*pi/180), param[1])
            
            bm.verts.new().co = (95*sin(angrange[len(angrange) - 1]*pi/180), 95*cos(angrange[len(angrange) - 1]*pi/180), param[1])
            angrange.reverse()
    
            for b in angrange[1:-1]:
                bm.verts.new().co = (98*sin(b*pi/180), 98*cos(b*pi/180), param[1])
    
            bm.faces.new(bm.verts[-160:])
            bm.faces.ensure_lookup_table()
            bm.faces[-1].material_index = param[2]

    bm.to_mesh(sprme)
    bm.free()
    return spro

def windnum(maxws, loc, scale, wr):
    txts = []
    matrot = Matrix.Rotation(-pi*0.075, 4, 'Z')
    direc = Vector((0, 1, 0))
    for i in range(2, 6):
        bpy.ops.object.text_add(view_align=False, enter_editmode=False, location=((i**2)/25)*scale*(matrot*direc))
        txt = bpy.context.active_object
        txt.data.body, txt.scale, txt.location[2] = '{:.1f}'.format((i**2)*maxws/25), (scale*0.05, scale*0.05, scale*0.05), scale*0.01
        bpy.ops.object.convert(target='MESH')
        bpy.ops.object.material_slot_add()
        txt.material_slots[-1].material = bpy.data.materials['wr-000000']
        txts.append(txt)
    objoin(txts + [wr]).name = 'Wind Rose'
    bpy.context.active_object['rpe']  = 'Wind_Plane'
    
def rgb2h(rgb):
    return colorsys.rgb_to_hsv(rgb[0]/255.0,rgb[1]/255.0,rgb[2]/255.0)[0]

def livisimacc(simnode):
    context = simnode.inputs['Context in'].links[0].from_node['Options']['Context']
    return(simnode.csimacc if context in ('Compliance', 'CBDM') else simnode.simacc)

def drawpoly(x1, y1, x2, y2, r, g, b, a):
#    bgl.glEnable(bgl.GL_BLEND)
#    bgl.glBlendFunc(bgl.GL_ONE, bgl.GL_CONSTANT_COLOR)
    bgl.glColor4f(r, g, b, a)
    bgl.glBegin(bgl.GL_POLYGON)
    bgl.glVertex2i(x1, y2)
    bgl.glVertex2i(x2, y2)
    bgl.glVertex2i(x2, y1)
    bgl.glVertex2i(x1, y1)
    bgl.glEnd()
#    bgl.glDisable(bgl.GL_BLEND)
    bgl.glColor4f(0.0, 0.0, 0.0, 1.0)
    
def drawtri(posx, posy, l, d, hscale, radius):
    r, g, b = colorsys.hsv_to_rgb(0.75 - l * 0.75, 1.0, 1.0)
    a = 0.9
    bgl.glEnable(bgl.GL_BLEND)
    bgl.glBegin(bgl.GL_POLYGON)
    bgl.glColor4f(r, g, b, a)
    bgl.glVertex2f(posx - l * 0.5  * hscale *(radius - 20)*sin(d*pi/180), posy - l * 0.5 * hscale * (radius - 20)*cos(d*pi/180)) 
    bgl.glVertex2f(posx + hscale * (l**0.5) *(radius/4 - 5)*cos(d*pi/180), posy - hscale * (l**0.5) *(radius/4 - 5)*sin(d*pi/180))    
    bgl.glVertex2f(posx + l**0.5 * hscale *(radius - 20)*sin(d*pi/180), posy + l**0.5 * hscale * (radius - 20)*cos(d*pi/180)) 
    bgl.glVertex2f(posx - hscale * (l**0.5) *(radius/4 - 5)*cos(d*pi/180), posy + hscale * (l**0.5) *(radius/4 - 5)*sin(d*pi/180))
    bgl.glEnd()
    bgl.glDisable(bgl.GL_BLEND)
    
def drawcircle(center, radius, resolution, fill, a, r, g, b):
    bgl.glColor4f(r, g, b, a)
    bgl.glEnable(bgl.GL_LINE_SMOOTH)
    bgl.glEnable(bgl.GL_BLEND);
    bgl.glBlendFunc(bgl.GL_SRC_ALPHA, bgl.GL_ONE_MINUS_SRC_ALPHA)
    bgl.glHint(bgl.GL_LINE_SMOOTH_HINT, bgl.GL_NICEST)
    bgl.glLineWidth (1.5)
    if fill:
        bgl.glBegin(bgl.GL_POLYGON)
    else:
        bgl.glBegin(bgl.GL_LINE_STRIP)

    for i in range(resolution+1):
        vec = Vector((cos(i/resolution*2*pi), sin(i/resolution*2*pi)))
        v = vec * radius + center
        bgl.glVertex2f(v.x, v.y)
    bgl.glEnd()

def drawbsdfcircle(centre, radius, resolution, fill, col, w, h, z, lw): 
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
    
def drawloop(x1, y1, x2, y2):
    bgl.glColor4f(0.0, 0.0, 0.0, 1.0)
    bgl.glBegin(bgl.GL_LINE_LOOP)
    bgl.glVertex2i(x1, y2)
    bgl.glVertex2i(x2, y2)
    bgl.glVertex2i(x2, y1)
    bgl.glVertex2i(x1, y1)
    bgl.glEnd()

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

def drawfont(text, fi, lencrit, height, x1, y1):
    blf.position(fi, x1, height - y1 - lencrit*26, 0)
    blf.draw(fi, text)

def xy2radial(c, pos, w, h):
    dx, dy = pos[0] - c[0], pos[1] - c[1]
    hypo = (((dx/w)**2 + (dy/h)**2)**0.5)
    at = math.atan((dy/h)/(dx/w))
    if dx == 0:
        azi = 0 if dy >= 0 else math.pi
    elif dx > 0:
        at = math.atan((dy/h)/(dx/w))
        azi = math.pi * 0.5 - at
    elif dx < 0:
        at = math.atan((dy/h)/(dx/w))
        azi = math.pi * 1.5 - at   
    return hypo, azi        

def mtx2vals(mtxlines, fwd, node, times):    
    for m, mtxline in enumerate(mtxlines):
        if 'NROWS' in mtxline:
            patches = int(mtxline.split('=')[1])
#        elif 'NCOLS' in mtxline:
#            hours = int(mtxline.split('=')[1])
        elif mtxline == '\n':
            startline = m + 1
            break

    sdoy = (times[0] - datetime.datetime(2015, 1, 1)).days
    shour = times[0].hour
    edoy = (times[-1] - datetime.datetime(2015, 1, 1)).days + 1
    ehour = times[-1].hour
    tothours = len(times)
    hours = [t.hour for t in times]
    invalidhours = [h for h in range(8760) if h < sdoy * 24 or h > edoy  * 24 or h%24 < shour or h%24 > ehour] 
    mtxlarray = array([0.333 * sum([float(lv) for lv in fval.split(" ")]) for fval in mtxlines[startline:] if fval != '\n'], dtype=float)
    mtxshapearray = mtxlarray.reshape(patches, 8760)
    mtxshapearray = ndelete(mtxshapearray, invalidhours, 1)
    vals = nsum(mtxshapearray, axis = 1)
    vvarray = transpose(mtxshapearray)
    vvlist = vvarray.tolist()
    vecvals = [[hours[x], (fwd+int(hours[x]/24))%7, *vvlist[x]] for x in range(tothours)]
    return(vecvals, vals)

def bres(scene, o):
    bm = bmesh.new()
    bm.from_mesh(o.data)
    if scene['liparams']['cp'] == '1':
        rtlayer = bm.verts.layers.int['cindex']
        reslayer = bm.verts.layers.float['res{}'.format(scene.frame_current)]
        res = [v[reslayer] for v in bm.verts if v[rtlayer] > 0]
    elif scene['liparams']['cp'] == '0':
        rtlayer = bm.faces.layers.int['cindex']
        reslayer = bm.faces.layers.float['res{}'.format(scene.frame_current)]
        res = [f[reslayer] for f in bm.faces if f[rtlayer] > 0]
    bm.free()
    return res
    
def framerange(scene, anim):
    if anim == 'Static':
        return(range(scene.frame_current, scene.frame_current +1))
    else:
        return(range(scene.frame_start, scene['liparams']['fe'] + 1))

def frameindex(scene, anim):
    if anim == 'Static':
        return(range(0, 1))
    else:
        return(range(0, scene.frame_end - scene.frame_start +1))

def retobjs(otypes):
    scene = bpy.context.scene
    validobs = [o for o in scene.objects if o.is_visible(scene)]
    if otypes == 'livig':
        return([o for o in validobs if o.type == 'MESH' and o.data.materials and not (o.parent and os.path.isfile(o.ies_name)) and not o.vi_type == '4' \
        and o.lires == 0 and o.get('VIType') not in ('SPathMesh', 'SunMesh', 'Wind_Plane', 'SkyMesh')])
    elif otypes == 'livigeno':
        return([o for o in validobs if o.type == 'MESH' and o.data.materials and not any([m.livi_sense for m in o.data.materials])])
    elif otypes == 'livigengeosel':
        return([o for o in validobs if o.type == 'MESH' and o.select == True and o.data.materials and not any([m.livi_sense for m in o.data.materials])])
    elif otypes == 'livil':
        return([o for o in validobs if (o.type == 'LAMP' or o.vi_type == '4') and o.layers[scene.active_layer] == True])
    elif otypes == 'livic':
        return([o for o in validobs if o.type == 'MESH' and li_calcob(o, 'livi') and o.lires == 0])
    elif otypes == 'livir':
        return([o for o in validobs if o.type == 'MESH' and True in [m.livi_sense for m in o.data.materials] and o.licalc])
    elif otypes == 'envig':
        return([o for o in scene.objects if o.type == 'MESH' and o.hide == False and not o.layers[1]])
    elif otypes == 'ssc':        
        return [o for o in validobs if o.type == 'MESH' and o.lires == 0 and o.data.materials and any([o.data.materials[poly.material_index].mattype == '1' for poly in o.data.polygons])]

def radmesh(scene, obs, export_op):
    for o in obs:
        for mat in o.data.materials:
            if mat['radentry'] and mat['radentry'].split(' ')[1] in ('light', 'mirror', 'antimatter') or mat.pport:
                export_op.report({'INFO'}, o.name+" has an antimatter, photon port, emission or mirror material. Basic export routine used with no modifiers.")
                o['merr'] = 1 
        selobj(scene, o)
#        selmesh('selenm')                        
#        if [edge for edge in o.data.edges if edge.select]:
#            export_op.report({'INFO'}, o.name+" has a non-manifold mesh. Basic export routine used with no modifiers.")
#            o['merr'] = 1
        if not o.get('merr'):
            o['merr'] = 0

def viewdesc(context):
    region = context.region
    width, height = region.width, region.height
    mid_x, mid_y = width/2, height/2
    return(mid_x, mid_y, width, height)
    
def skfpos(o, frame, vis):
    vcos = [o.matrix_world*o.data.shape_keys.key_blocks[str(frame)].data[v].co for v in vis]
    maxx = max([vco[0] for vco in vcos])
    minx = min([vco[0] for vco in vcos])
    maxy = max([vco[1] for vco in vcos])
    miny = min([vco[1] for vco in vcos])
    maxz = max([vco[2] for vco in vcos])
    minz = min([vco[2] for vco in vcos])
    return mathutils.Vector(((maxx + minx) * 0.5, (maxy + miny) * 0.5, (maxz + minz) * 0.5))

def selmesh(sel):
    if bpy.context.active_object.mode != 'EDIT':
        bpy.ops.object.mode_set(mode = 'EDIT')        
    if sel == 'selenm':
        bpy.ops.mesh.select_mode(type="EDGE")
        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.mesh.select_non_manifold()
    elif sel == 'desel':
        bpy.ops.mesh.select_all(action='DESELECT')
    elif sel in ('delf', 'rd'):
        if sel == 'delf':
            bpy.ops.mesh.delete(type = 'FACE')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.remove_doubles()
        bpy.ops.mesh.select_all(action='DESELECT')
    elif sel =='dele':
        bpy.ops.mesh.delete(type = 'EDGE')
    elif sel =='delv':
        bpy.ops.mesh.delete(type = 'VERT')
    elif sel == 'mc':
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.vert_connect_concave()
        bpy.ops.mesh.select_all(action='DESELECT')
    elif sel == 'mp':
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.vert_connect_nonplanar(angle_limit=0.001)
        bpy.ops.mesh.select_all(action='DESELECT')
    elif sel in ('SELECT', 'INVERT', 'PASS'):
        if sel in ('SELECT', 'INVERT'):
            bpy.ops.mesh.select_all(action=sel)    
        bpy.ops.object.vertex_group_assign()
    bpy.ops.object.mode_set(mode = 'OBJECT')
    
def retdp(mres, dp):
    try:
        dp = 0 if ceil(log10(100/mres)) < 0 or not dp else ceil(log10(100/mres))
    except:
        dp = 0
    return dp

def draw_index_distance(posis, res, fontsize, fontcol, shadcol, distances):
    if len(distances):
        try:
            dp = 0 if max(res) > 100 else 1
            nres = ['{:.{precision}f}'.format(r, precision = dp) for r in res]
            fsdist = (fontsize/distances).astype(int8)
            xposis = posis[:,0]
            yposis = posis[:,1]
#            [(blf.size(0, fontsize, fsdist[ri]), blf.position(0, xposis[ri] - int(0.5*blf.dimensions(0, nr)[0]), yposis[ri] - int(0.5 * blf.dimensions(0, nr)[1]), 0.99), blf.draw(0, nr)) for ri, nr in enumerate(nres)]
            for ri, nr in enumerate(nres):
                if distances[ri] > 1.25:
                    blf.size(0, fsdist[ri], bpy.context.user_preferences.system.dpi)
                    blf.position(0, xposis[ri] - int(0.5*blf.dimensions(0, nr)[0]), yposis[ri] - int(0.5 * blf.dimensions(0, nr)[1]), 0.99)
                    blf.draw(0, nr)
        except Exception as e:
            print(e)

def draw_index(posis, res, fontsize, fontcol, shadcol): 
    nres = ['{}'.format(format(r, '.{}f'.format(retdp(max(res), 0)))) for ri, r in enumerate(res)]    
    for ri, nr in enumerate(nres):
        blf.position(0, posis[ri][0] - int(0.5*blf.dimensions(0, nr)[0]), posis[ri][1] - int(0.5 * blf.dimensions(0, nr)[1]), 0.99)        
        blf.draw(0, nr)        
    blf.disable(0, 4)
    
def draw_time(pos, time, fontsize, fontcol, shadcol):
    blf.position(0, pos[0], pos[1] - blf.dimensions(0, time)[1] * 0.5, 0)
    blf.draw(0, time)
    blf.disable(0, 4)
    
def blf_props(scene, width, height):
    blf.enable(0, 2)
    blf.clipping(0, 0, 0, width, height)
    if scene.vi_display_rp_sh:
        blf.enable(0, 4)
        blf.shadow(0, 3, *scene.vi_display_rp_fsh)
    bgl.glColor4f(*scene.vi_display_rp_fc)
    blf.size(0, scene.vi_display_rp_fs, int(width/20))
    
def blf_unprops():
    blf.disable(0, 2)
    blf.disable(0, 4)
    bgl.glColor4f(0, 0, 0, 1)
    
def edgelen(ob, edge):
    omw = ob.matrix_world
    vdiff = omw * (ob.data.vertices[edge.vertices[0]].co - ob.data.vertices[edge.vertices[1]].co)
    mathutils.Vector(vdiff).length

def sunpath1(self, context):
    sunpath()

def sunpath2(scene):
    sunpath()

def sunpath():
    scene = bpy.context.scene
    suns = [ob for ob in scene.objects if ob.get('VIType') == 'Sun']
    skyspheres = [ob for ob in scene.objects if ob.get('VIType') == 'SkyMesh']
    
    if suns and 0 in (suns[0]['solhour'] == scene.solhour, suns[0]['solday'] == scene.solday):
        sunobs = [ob for ob in scene.objects if ob.get('VIType') == 'SunMesh']
        spathobs = [ob for ob in scene.objects if ob.get('VIType') == 'SPathMesh']
        beta, phi = solarPosition(scene.solday, scene.solhour, scene.latitude, scene.longitude)[2:]
        if spathobs:
            suns[0].location.z = 100 * sin(beta)
            suns[0].location.x = -(100**2 - (suns[0].location.z)**2)**0.5 * sin(phi)
            suns[0].location.y = -(100**2 - (suns[0].location.z)**2)**0.5 * cos(phi)
        suns[0].rotation_euler = pi * 0.5 - beta, 0, -phi

        if scene.render.engine == 'CYCLES':
            if scene.world.node_tree:
                for stnode in [no for no in scene.world.node_tree.nodes if no.bl_label == 'Sky Texture']:
                    stnode.sun_direction = -sin(phi), -cos(phi), sin(beta)
            if suns[0].data.node_tree:
                for blnode in [node for node in suns[0].data.node_tree.nodes if node.bl_label == 'Blackbody']:
                    blnode.inputs[0].default_value = 2500 + 3000*sin(beta)**0.5 if beta > 0 else 2500
                for emnode in [node for node in suns[0].data.node_tree.nodes if node.bl_label == 'Emission']:
                    emnode.inputs[1].default_value = 10 * sin(beta)**0.5 if beta > 0 else 0
            if sunobs and sunobs[0].data.materials[0].node_tree:
                for smblnode in [node for node in sunobs[0].data.materials[0].node_tree.nodes if sunobs[0].data.materials and node.bl_label == 'Blackbody']:
                    smblnode.inputs[0].default_value = 2500 + 3000*sin(beta)**0.5 if beta > 0 else 2500
            if skyspheres and not skyspheres[0].hide and skyspheres[0].data.materials[0].node_tree:
                for stnode in [no for no in skyspheres[0].data.materials[0].node_tree.nodes if no.bl_label == 'Sky Texture']:
                    stnode.sun_direction = sin(phi), -cos(phi), sin(beta)

        suns[0]['solhour'], suns[0]['solday'] = scene.solhour, scene.solday
        return

def epwlatilongi(scene, node):
    with open(node.weather, "r") as epwfile:
        fl = epwfile.readline()
        latitude, longitude = float(fl.split(",")[6]), float(fl.split(",")[7])
    return latitude, longitude

#Compute solar position (altitude and azimuth in degrees) based on day of year (doy; integer), local solar time (lst; decimal hours), latitude (lat; decimal degrees), and longitude (lon; decimal degrees).
def solarPosition(doy, lst, lat, lon):
    #Set the local standard time meridian (lsm) (integer degrees of arc)
    lsm = round(lon/15, 0)*15
    #Approximation for equation of time (et) (minutes) comes from the Wikipedia article on Equation of Time
    b = 2*pi*(doy-81)/364
    et = 9.87 * sin(2*b) - 7.53 * cos(b) - 1.5 * sin(b)
    #The following formulas adapted from the 2005 ASHRAE Fundamentals, pp. 31.13-31.16
    #Conversion multipliers
    degToRad = 2*pi/360
    radToDeg = 1/degToRad
    #Apparent solar time (ast)
    if lon > lsm: 
        ast = lst + et/60 - (lsm-lon)/15
    else:
        ast = lst + et/60 + (lsm-lon)/15
    #Solar declination (delta) (radians)
    delta = degToRad*23.45 * sin(2*pi*(284+doy)/365)
    #Hour angle (h) (radians)
    h = degToRad*15 * (ast-12)
     #Local latitude (l) (radians)
    l = degToRad*lat
    #Solar altitude (beta) (radians)
    beta = asin(cos(l) * cos(delta) * cos(h) + sin(l) * sin(delta))
    #Solar azimuth phi (radians)
    phi = acos((sin(beta) * sin(l) - sin(delta))/(cos(beta) * cos(l)))
    #Convert altitude and azimuth from radians to degrees, since the Spatial Analyst's Hillshade function inputs solar angles in degrees
    altitude = radToDeg*beta
    phi = 2*pi - phi if ast<=12 or ast >= 24 else phi
    azimuth = radToDeg*phi
    return([altitude, azimuth, beta, phi])
    
def solarRiseSet(doy, beta, lat, lon, riseset):
    degToRad = 2*pi/360
    radToDeg = 1/degToRad
    delta = degToRad*23.45 * sin(2*pi*(284+doy)/365)
    l = degToRad*lat
    try:
        phi = acos((sin(beta) * sin(l) - sin(delta))/(cos(beta) * cos(l)))
        phi = pi - phi if riseset == 'morn' else pi + phi
    except:
        phi = 0    
    return(phi*radToDeg)

def set_legend(ax):
    l = ax.legend(borderaxespad = -4)
    plt.setp(l.get_texts(), fontsize=8)

def wr_axes():
    fig = plt.figure(figsize=(8, 8), dpi=150, facecolor='w', edgecolor='w')
    rect = [0.1, 0.1, 0.8, 0.8]
    ax = WindroseAxes(fig, rect, facecolor='w')
    fig.add_axes(ax)
    return(fig, ax)

def skframe(pp, scene, oblist):
    for frame in range(scene['liparams']['fs'], scene['liparams']['fe'] + 1):
        scene.frame_set(frame)
        for o in [o for o in oblist if o.data.shape_keys]:
            for shape in o.data.shape_keys.key_blocks:
                if shape.name.isdigit():
                    shape.value = shape.name == str(frame)
                    shape.keyframe_insert("value")

def gentarget(tarnode, result):
    if tarnode.stat == '0':
        res = sum(result)/len(result)
    elif tarnode.stat == '1':
        res = max(result)
    elif tarnode.stat == '2':
        res = min(result)
    elif tarnode.stat == '3':
        res = sum(result)

    if tarnode.value > res and tarnode.ab == '0':
        return(1)
    elif tarnode.value < res and tarnode.ab == '1':
        return(1)
    else:
        return(0)

def selobj(scene, geo):
    if scene.objects.active and scene.objects.active.hide == 'False':
        bpy.ops.object.mode_set(mode = 'OBJECT') 
    for ob in scene.objects:
        ob.select = True if ob == geo else False
    scene.objects.active = geo

def nodeid(node):
    for ng in bpy.data.node_groups:
        if node in ng.nodes[:]:
            return node.name+'@'+ng.name

def nodecolour(node, prob):
    (node.use_custom_color, node.color) = (1, (1.0, 0.3, 0.3)) if prob else (0, (1.0, 0.3, 0.3))
    if prob:
        node.hide = False
    return not prob

def remlink(node, links):
    for link in links:
        bpy.data.node_groups[node['nodeid'].split('@')[1]].links.remove(link)

def sockhide(node, lsocknames):
    try:
        for ins in [insock for insock in node.inputs if insock.name in lsocknames]:
            node.outputs[ins.name].hide = True if ins.links else False
        for outs in [outsock for outsock in node.outputs if outsock.name in lsocknames]:
            node.inputs[outs.name].hide = True if outs.links else False
    except Exception as e:
        print('sockhide', e)

def socklink(sock, ng):
    try:
        valid1 = sock.valid if not sock.get('valid') else sock['valid']
        for link in sock.links:
            valid2 = link.to_socket.valid if not link.to_socket.get('valid') else link.to_socket['valid'] 
            valset = set(valid1)&set(valid2) 
            if not valset or len(valset) < min((len(valid1), len(valid2))):# or sock.node.use_custom_color:
                bpy.data.node_groups[ng].links.remove(link)
    except:
        if sock.links:
            bpy.data.node_groups[ng].links.remove(sock.links[-1])
            
def uvsocklink(sock, ng):
    try:
        uv1 = sock.uvalue
        for link in sock.links:
            uv2 = link.to_socket.uvalue 
            if uv1 != uv2:
                bpy.data.node_groups[ng].links.remove(link)
    except:
        pass
    
def rettimes(ts, fs, us):
    tot = range(min(len(ts), len(fs), len(us)))
    fstrings, ustrings, tstrings = [[] for t in tot],  [[] for t in tot], ['Through: {}/{}'.format(dtdf(ts[t]).month, dtdf(ts[t]).day) for t in tot]
    for t in tot:
        fstrings[t]= ['For: '+''.join(f.strip()) for f in fs[t].split(' ') if f.strip(' ') != '']
        for uf, ufor in enumerate(us[t].split(';')):
            ustrings[t].append([])
            for ut, utime in enumerate(ufor.split(',')):
                ustrings[t][uf].append(['Until: '+','.join([u.strip() for u in utime.split(' ') if u.strip(' ')])])
    return(tstrings, fstrings, ustrings)

def retdates(sdoy, edoy, y):
    (y1, y2) = (y, y) if edoy >= sdoy else (y - 1, y)
    sdate = datetime.datetime(y1, 1, 1) + datetime.timedelta(sdoy - 1)
    edate = datetime.datetime(y2, 1, 1) + datetime.timedelta(edoy - 1)
    return(sdate, edate)
        
def li_calcob(ob, li):
    if not ob.data.materials:
        return False
    else:
        ob.licalc = 1 if [face.index for face in ob.data.polygons if ob.data.materials[face.material_index].mattype == '1'] else 0
        return ob.licalc

# FloVi functions
def fvboundwrite(o):
    boundary = ''
    for mat in o.data.materials:        
        boundary += "  {}\n  {{\n    type {};\n    faces\n    (\n".format(mat.name, ("wall", "patch", "patch", "symmetryPlane", "empty")[int(mat.flovi_bmb_type)])#;\n\n"
        faces = [face for face in o.data.polygons if o.data.materials[face.material_index] == mat]
        for face in faces:
            boundary += "      ("+" ".join([str(v) for v in face.vertices])+")\n"
        boundary += "    );\n  }\n"
    boundary += ");\n\nmergePatchPairs\n(\n);"
    return boundary
    
def fvbmwrite(o, expnode):
    omw, bmovs = o.matrix_world, [vert for vert in o.data.vertices]
    xvec, yvec, zvec = (omw*bmovs[3].co - omw*bmovs[0].co).normalized(), (omw*bmovs[2].co - omw*bmovs[3].co).normalized(), (omw*bmovs[4].co - omw*bmovs[0].co).normalized() 
    ofvpos = [[(omw*bmov.co - omw*bmovs[0].co)*vec for vec in (xvec, yvec, zvec)] for bmov in bmovs]
    bmdict = "FoamFile\n  {\n  version     2.0;\n  format      ascii;\n  class       dictionary;\n  object      blockMeshDict;\n  }\n\nconvertToMeters 1.0;\n\n" 
    bmdict += "vertices\n(\n" + "\n".join(["  ({0:.3f} {1:.3f} {2:.3f})" .format(*ofvpo) for ofvpo in ofvpos]) +"\n);\n\n"
    bmdict += "blocks\n(\n  hex (0 3 2 1 4 7 6 5) ({} {} {}) simpleGrading ({} {} {})\n);\n\n".format(expnode.bm_xres, expnode.bm_yres, expnode.bm_zres, expnode.bm_xgrad, expnode.bm_ygrad, expnode.bm_zgrad) 
    bmdict += "edges\n(\n);\n\n"  
    bmdict += "boundary\n(\n" 
    bmdict += fvboundwrite(o)
    return bmdict
    
def fvblbmgen(mats, ffile, vfile, bfile, meshtype):
    scene = bpy.context.scene
    matfacedict = {mat.name:[0, 0] for mat in mats}
    
    for line in bfile.readlines():
        if line.strip() in matfacedict:
            mat = line.strip()
        elif '_' in line and line.strip().split('_')[1] in matfacedict:
            mat = line.strip().split('_')[1]
        if 'nFaces' in line:
            matfacedict[mat][1] = int(line.split()[1].strip(';'))
        if 'startFace' in line:
            matfacedict[mat][0] = int(line.split()[1].strip(';'))
    bobs = [ob for ob in scene.objects if ob.get('VIType') and ob['VIType'] == 'FloViMesh']
    
    if bobs:
        o = bobs[0]
        selobj(scene, o)
        while o.data.materials:
            bpy.ops.object.material_slot_remove()
    else:
        bpy.ops.object.add(type='MESH', layers=(False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, True))
        o = bpy.context.object
        o['VIType'] = 'FloViMesh'
    
    o.name = meshtype
    for mat in mats:
        if mat.name not in o.data.materials:
            bpy.ops.object.material_slot_add()
            o.material_slots[-1].material = mat 
    matnamedict = {mat.name: m for  m, mat in enumerate(o.data.materials)}
    
    bm = bmesh.new()
    for line in [line for line in vfile.readlines() if line[0] == '(' and len(line.split(' ')) == 3]:
        bm.verts.new().co = [float(vpos) for vpos in line[1:-2].split(' ')]
    if hasattr(bm.verts, "ensure_lookup_table"):
        bm.verts.ensure_lookup_table()
    for l, line in enumerate([line for line in ffile.readlines() if '(' in line and line[0].isdigit() and len(line.split(' ')) == int(line[0])]):
        newf = bm.faces.new([bm.verts[int(fv)] for fv in line[2:-2].split(' ')])
        for facerange in matfacedict.items():
            if l in range(facerange[1][0], facerange[1][0] + facerange[1][1]):
                newf.material_index = matnamedict[facerange[0]]
    bm.to_mesh(o.data)
    bm.free()

def fvbmr(scene, o):
    points = '{\n    version     2.0;\n    format      ascii;\n    class       vectorField;\n    location    "constant/polyMesh";\n    object      points;\n}\n\n{}\n(\n'.format(len(o.data.verts))
    points += ''.join(['({} {} {})\n'.format(o.matrix_world * v.co) for v in o.data.verts]) + ')'
    with open(os.path.join(scene['flparams']['ofcpfilebase'], 'points'), 'r') as pfile:
        pfile.write(points)
    faces = '{\n    version     2.0;\n    format      ascii;\n    class       faceList;\n    location    "constant/polyMesh";\n    object      faces;\n}\n\n{}\n(\n'.format(len(o.data.faces))
    faces += ''.join(['({} {} {} {})\n'.format(f.vertices) for f in o.data.faces]) + ')'
    with open(os.path.join(scene['flparams']['ofcpfilebase'], 'faces'), 'r') as ffile:
        ffile.write(faces)
    
def fvvarwrite(scene, obs, node):
    '''Turbulence modelling: k and epsilon required for kEpsilon, k and omega required for kOmega, nutilda required for SpalartAllmaras, nut required for all
        Bouyancy modelling: T''' 
    (pentry, Uentry, nutildaentry, nutentry, kentry, eentry, oentry) = ["FoamFile\n{{\n  version     2.0;\n  format      ascii;\n  class       vol{}Field;\n  object      {};\n}}\n\ndimensions [0 {} {} 0 0 0 0];\ninternalField   uniform {};\n\nboundaryField\n{{\n".format(*var) for var in (('Scalar', 'p', '2', '-2', '{}'.format(node.pval)), ('Vector', 'U', '1', '-1' , '({} {} {})'.format(*node.uval)), ('Scalar', 'nuTilda', '2', '-1' , '{}'.format(node.nutildaval)), ('Scalar', 'nut', '2', '-1' , '{}'.format(node.nutval)), 
    ('Scalar', 'k', '2', '-2' , '{}'.format(node.kval)), ('Scalar', 'epsilon', '2', '-3' , '{}'.format(node.epval)), ('Scalar', 'omega', '0', '-1' , '{}'.format(node.oval)))]
    
    for o in obs:
        for mat in o.data.materials: 
            matname = '{}_{}'.format(o.name, mat.name) if o.vi_type == '3' else mat.name 
            if mat.mattype == '2':
                pentry += mat.fvmat(matname, 'p')
                Uentry += mat.fvmat(matname, 'U')
                if node.solver != 'icoFoam':
                    nutentry += mat.fvmat(matname, 'nut')
                    if node.turbulence ==  'SpalartAllmaras':
                        nutildaentry += mat.fvmat(matname, 'nutilda')
                    elif node.turbulence ==  'kEpsilon':
                        kentry += mat.fvmat(matname, 'k')
                        eentry += mat.fvmat(matname, 'e')
                    elif node.turbulence ==  'kOmega':
                        kentry += mat.fvmat(matname, 'k')
                        oentry += mat.fvmat(matname, 'o')

    pentry += '}'
    Uentry += '}'
    nutentry += '}'
    kentry += '}'
    eentry += '}'
    oentry += '}'
    
    with open(os.path.join(scene['flparams']['of0filebase'], 'p'), 'w') as pfile:
        pfile.write(pentry)
    with open(os.path.join(scene['flparams']['of0filebase'], 'U'), 'w') as Ufile:
        Ufile.write(Uentry)
    if node.solver != 'icoFoam':
        with open(os.path.join(scene['flparams']['of0filebase'], 'nut'), 'w') as nutfile:
            nutfile.write(nutentry)
        if node.turbulence == 'SpalartAllmaras':
            with open(os.path.join(scene['flparams']['of0filebase'], 'nuTilda'), 'w') as nutildafile:
                nutildafile.write(nutildaentry)
        if node.turbulence == 'kEpsilon':
            with open(os.path.join(scene['flparams']['of0filebase'], 'k'), 'w') as kfile:
                kfile.write(kentry)
            with open(os.path.join(scene['flparams']['of0filebase'], 'epsilon'), 'w') as efile:
                efile.write(eentry)
        if node.turbulence == 'kOmega':
            with open(os.path.join(scene['flparams']['of0filebase'], 'k'), 'w') as kfile:
                kfile.write(kentry)
            with open(os.path.join(scene['flparams']['of0filebase'], 'omega'), 'w') as ofile:
                ofile.write(oentry)
                
def fvmattype(mat, var):
    if mat.flovi_bmb_type == '0':
        matbptype = ['zeroGradient'][int(mat.flovi_bmwp_type)]
        matbUtype = ['fixedValue'][int(mat.flovi_bmwu_type)]
    elif mat.flovi_bmb_type in ('1', '2'):
        matbptype = ['freestreamPressure'][int(mat.flovi_bmiop_type)]
        matbUtype = ['fixedValue'][int(mat.flovi_bmiou_type)]
    elif mat.flovi_bmb_type == '3':
        matbptype = 'empty'
        matbUtype = 'empty'
    
def fvcdwrite(solver, dt, et):
    pw = 0 if solver == 'icoFoam' else 1
    return 'FoamFile\n{\n  version     2.0;\n  format      ascii;\n  class       dictionary;\n  location    "system";\n  object      controlDict;\n}\n\n' + \
            'application     {};\nstartFrom       startTime;\nstartTime       0;\nstopAt          endTime;\nendTime         {};\n'.format(solver, et)+\
            'deltaT          {};\nwriteControl    timeStep;\nwriteInterval   {};\npurgeWrite      {};\nwriteFormat     ascii;\nwritePrecision  6;\n'.format(dt, 1, pw)+\
            'writeCompression off;\ntimeFormat      general;\ntimePrecision   6;\nrunTimeModifiable true;\n\n'

def fvsolwrite(node):
    ofheader = 'FoamFile\n{\n  version     2.0;\n  format      ascii;\n  class       dictionary;\n  location    "system";\n  object    fvSolution;\n}\n\n' + \
        'solvers\n{\n  p\n  {\n    solver          PCG;\n    preconditioner  DIC;\n    tolerance       1e-06;\n    relTol          0;\n  }\n\n' + \
        '  "(U|k|epsilon|omega|R|nuTilda)"\n  {\n    solver          smoothSolver;\n    smoother        symGaussSeidel;\n    tolerance       1e-05;\n    relTol          0;  \n  }\n}\n\n'
    if node.solver == 'icoFoam':
        ofheader += 'PISO\n{\n  nCorrectors     2;\n  nNonOrthogonalCorrectors 0;\n  pRefCell        0;\n  pRefValue       0;\n}\n\n' + \
        'solvers\n{\n    p\n    {\n        solver          GAMG;\n        tolerance       1e-06;\n        relTol          0.1;\n        smoother        GaussSeidel;\n' + \
        '        nPreSweeps      0;\n        nPostSweeps     2;\n        cacheAgglomeration true;\n        nCellsInCoarsestLevel 10;\n        agglomerator    faceAreaPair;\n'+ \
        '        mergeLevels     1;\n    }\n\n    U\n    {\n        solver          smoothSolver;\n        smoother        GaussSeidel;\n        nSweeps         2;\n' + \
        '        tolerance       1e-08;\n        relTol          0.1;\n    }\n\n    nuTilda\n    {\n        solver          smoothSolver;\n        smoother        GaussSeidel;\n' + \
        '        nSweeps         2;\n        tolerance       1e-08;\n        relTol          0.1;\n    }\n}\n\n'
    elif node.solver == 'simpleFoam':   
        ofheader += 'SIMPLE\n{{\n  nNonOrthogonalCorrectors 0;\n  pRefCell        0;\n  pRefValue       0;\n\n    residualControl\n  {{\n    "(p|U|k|epsilon|omega|nut|nuTilda)" {};\n  }}\n}}\n'.format(node.convergence)
        ofheader += 'relaxationFactors\n{\n    fields\n    {\n        p               0.3;\n    }\n    equations\n    {\n' + \
            '        U               0.7;\n        k               0.7;\n        epsilon           0.7;\n      omega           0.7;\n        nuTilda           0.7;\n    }\n}\n\n'
#        if node.turbulence == 'kEpsilon':
#            ofheader += 'relaxationFactors\n{\n    fields\n    {\n        p               0.3;\n    }\n    equations\n    {\n' + \
#            '        U               0.7;\n        k               0.7;\n        epsilon           0.7;\n    }\n}\n\n'
#        elif node.turbulence == 'kOmega':
#            ofheader += 'relaxationFactors\n{\n    fields\n    {\n        p               0.3;\n    }\n    equations\n    {\n' + \
#            '        U               0.7;\n        k               0.7;\n        omega           0.7;\n    }\n}\n\n'
#        elif node.turbulence == 'SpalartAllmaras':
#            ofheader += 'relaxationFactors\n{\n    fields\n    {\n        p               0.3;\n    }\n    equations\n    {\n' + \
#            '        U               0.7;\n        k               0.7;\n        nuTilda           0.7;\n    }\n}\n\n'
    return ofheader

def fvschwrite(node):
    ofheader = 'FoamFile\n{\n  version     2.0;\n  format      ascii;\n  class       dictionary;\n  location    "system";\n  object    fvSchemes;\n}\n\n'
    if node.solver == 'icoFoam':
        return ofheader + 'ddtSchemes\n{\n  default         Euler;\n}\n\ngradSchemes\n{\n  default         Gauss linear;\n  grad(p)         Gauss linear;\n}\n\n' + \
            'divSchemes\n{\n  default         none;\n  div(phi,U)      Gauss linear;\n}\n\nlaplacianSchemes\n{\n  default         Gauss linear orthogonal;\n}\n\n' + \
            'interpolationSchemes\n{\n  default         linear;\n}\n\n' + \
            'snGradSchemes{  default         orthogonal;}\n\nfluxRequired{  default         no;  p;\n}'
    else:
        ofheader += 'ddtSchemes\n{\n    default         steadyState;\n}\n\ngradSchemes\n{\n    default         Gauss linear;\n}\n\ndivSchemes\n{\n    '
        if node.turbulence == 'kEpsilon':
            ofheader += 'default         none;\n    div(phi,U)   bounded Gauss upwind;\n    div(phi,k)      bounded Gauss upwind;\n    div(phi,epsilon)  bounded Gauss upwind;\n    div((nuEff*dev(T(grad(U))))) Gauss linear;\n}\n\n'
        elif node.turbulence == 'kOmega':
            ofheader += 'default         none;\n    div(phi,U)   bounded Gauss upwind;\n    div(phi,k)      bounded Gauss upwind;\n    div(phi,omega)  bounded Gauss upwind;\n    div((nuEff*dev(T(grad(U))))) Gauss linear;\n}\n\n'
        elif node.turbulence == 'SpalartAllmaras':
            ofheader += 'default         none;\n    div(phi,U)   bounded Gauss linearUpwind grad(U);\n    div(phi,nuTilda)      bounded Gauss linearUpwind grad(nuTilda);\n    div((nuEff*dev(T(grad(U))))) Gauss linear;\n}\n\n'
        ofheader += 'laplacianSchemes\n{\n    default         Gauss linear corrected;\n}\n\n' + \
        'interpolationSchemes\n{\n    default         linear;\n}\n\nsnGradSchemes\n{\n    default         corrected;\n}\n\n' + \
        'fluxRequired\n{\n    default         no;\n    p               ;\n}\n'
    return ofheader

def fvtppwrite(solver):
    ofheader = 'FoamFile\n{\n    version     2.0;\n    format      ascii;\n    class       dictionary;\n    location    "constant";\n    object      transportProperties;\n}\n\n'
    if solver == 'icoFoam':
        return ofheader + 'nu              nu [ 0 2 -1 0 0 0 0 ] 0.01;\n'
    else:
        return ofheader + 'transportModel  Newtonian;\n\nrho             rho [ 1 -3 0 0 0 0 0 ] 1;\n\nnu              nu [ 0 2 -1 0 0 0 0 ] 1e-05;\n\n' + \
        'CrossPowerLawCoeffs\n{\n    nu0             nu0 [ 0 2 -1 0 0 0 0 ] 1e-06;\n    nuInf           nuInf [ 0 2 -1 0 0 0 0 ] 1e-06;\n    m               m [ 0 0 1 0 0 0 0 ] 1;\n' + \
        '    n               n [ 0 0 0 0 0 0 0 ] 1;\n}\n\n' + \
        'BirdCarreauCoeffs\n{\n    nu0             nu0 [ 0 2 -1 0 0 0 0 ] 1e-06;\n    nuInf           nuInf [ 0 2 -1 0 0 0 0 ] 1e-06;\n' + \
        '    k               k [ 0 0 1 0 0 0 0 ] 0;\n    n               n [ 0 0 0 0 0 0 0 ] 1;\n}'
        
def fvraswrite(turb):
    ofheader = 'FoamFile\n{\n    version     2.0;\n    format      ascii;\n    class       dictionary;\n    location    "constant";\n    object      RASProperties;\n}\n\n'
    return ofheader + 'RASModel        {};\n\nturbulence      on;\n\nprintCoeffs     on;\n'.format(turb)
    
def fvshmwrite(node, o, **kwargs):    
    layersurf = '({}|{})'.format(kwargs['ground'][0].name, o.name) if kwargs and kwargs['ground'] else o.name 
    ofheader = 'FoamFile\n{\n    version     2.0;\n    format      ascii;\n    class       dictionary;\n    object      snappyHexMeshDict;\n}\n\n'
    ofheader += 'castellatedMesh    {};\nsnap    {};\naddLayers    {};\ndebug    {};\n\n'.format('true', 'true', 'true', 0)
    ofheader += 'geometry\n{{\n    {0}.obj\n    {{\n        type triSurfaceMesh;\n        name {0};\n    }}\n}};\n\n'.format(o.name)
    ofheader += 'castellatedMeshControls\n{{\n  maxLocalCells {};\n  maxGlobalCells {};\n  minRefinementCells {};\n  maxLoadUnbalance 0.10;\n  nCellsBetweenLevels {};\n'.format(node.lcells, node.gcells, int(node.gcells/100), node.ncellsbl)
    ofheader += '  features\n  (\n    {{\n      file "{}.eMesh";\n      level {};\n    }}\n  );\n\n'.format(o.name, node.level)
    ofheader += '  refinementSurfaces\n  {{\n    {}\n    {{\n      level ({} {});\n    }}\n  }}\n\n  '.format(o.name, node.surflmin, node.surflmax) 
    ofheader += '  resolveFeatureAngle 30;\n  refinementRegions\n  {}\n\n'
    ofheader += '  locationInMesh ({} {} {});\n  allowFreeStandingZoneFaces true;\n}}\n\n'.format(0.1, 0.1, 0.1)
    ofheader += 'snapControls\n{\n  nSmoothPatch 3;\n  tolerance 2.0;\n  nSolveIter 30;\n  nRelaxIter 5;\n  nFeatureSnapIter 10;\n  implicitFeatureSnap false;\n  explicitFeatureSnap true;\n  multiRegionFeatureSnap false;\n}\n\n'
    ofheader += 'addLayersControls\n{{\n  relativeSizes true;\n  layers\n  {{\n    "{}.*"\n    {{\n      nSurfaceLayers {};\n    }}\n  }}\n\n'.format(layersurf, node.layers)
    ofheader += '  expansionRatio 1.0;\n  finalLayerThickness 0.3;\n  minThickness 0.1;\n  nGrow 0;\n  featureAngle 60;\n  slipFeatureAngle 30;\n  nRelaxIter 3;\n  nSmoothSurfaceNormals 1;\n  nSmoothNormals 3;\n' + \
                '  nSmoothThickness 10;\n  maxFaceThicknessRatio 0.5;\n  maxThicknessToMedialRatio 0.3;\n  minMedianAxisAngle 90;\n  nBufferCellsNoExtrude 0;\n  nLayerIter 50;\n}\n\n'
    ofheader += 'meshQualityControls\n{\n  #include "meshQualityDict"\n  nSmoothScale 4;\n  errorReduction 0.75;\n}\n\n'
    ofheader += 'writeFlags\n(\n  scalarLevels\n  layerSets\n  layerFields\n);\n\nmergeTolerance 1e-6;\n'
    return ofheader

def fvmqwrite():
    ofheader = 'FoamFile\n{\n  version     2.0;\n  format      ascii;\n  class       dictionary;\n  object      meshQualityDict;\n}\n\n'
    ofheader += '#include "$WM_PROJECT_DIR/etc/caseDicts/meshQualityDict"'
    return ofheader
    
def fvsfewrite(oname):
    ofheader = 'FoamFile\n{\n  version     2.0;\n  format      ascii;\n  class       dictionary;\n  object      surfaceFeatureExtractDict;\n}\n\n'
    ofheader += '{}.obj\n{{\n  extractionMethod    extractFromSurface;\n\n  extractFromSurfaceCoeffs\n  {{\n    includedAngle   150;\n  }}\n\n    writeObj\n    yes;\n}}\n'.format(oname)
    return ofheader

def fvobjwrite(scene, o, bmo):
    objheader = '# FloVi obj exporter\no {}\n'.format(o.name)
    objheader = '# FloVi obj exporter\n'
    bmomw, bmovs = bmo.matrix_world, [vert for vert in bmo.data.vertices]
    omw, ovs = o.matrix_world, [vert for vert in o.data.vertices]
    xvec, yvec, zvec = (bmomw*bmovs[3].co - bmomw*bmovs[0].co).normalized(), (bmomw*bmovs[2].co - bmomw*bmovs[3].co).normalized(), (bmomw*bmovs[4].co - bmomw*bmovs[0].co).normalized() 
    ofvpos = [[(omw*ov.co - bmomw*bmovs[0].co)*vec for vec in (xvec, yvec, zvec)] for ov in ovs]
    bm = bmesh.new()
    bm.from_mesh(o.data)
    vcos = ''.join(['v {} {} {}\n'.format(*ofvpo) for ofvpo in ofvpos])
    with open(os.path.join(scene['flparams']['ofctsfilebase'], '{}.obj'.format(o.name)), 'w') as objfile:
        objfile.write(objheader+vcos)
        for m, mat in enumerate(o.data.materials):
            objfile.write('g {}\n'.format(mat.name) + ''.join(['f {} {} {}\n'.format(*[v.index + 1 for v in f.verts]) for f in bmesh.ops.triangulate(bm, faces = bm.faces)['faces'] if f.material_index == m]))
        objfile.write('#{}'.format(len(bm.faces)))
    bm.free()
    
def sunposenvi(scene, sun, dirsol, difsol, mdata, ddata, hdata):
    frames = range(scene.frame_start, scene.frame_end)
    times = [datetime.datetime(2015, mdata[hi], ddata[hi], h - 1, 0) for hi, h in enumerate(hdata)]
    solposs = [solarPosition(time.timetuple()[7], time.hour + (time.minute)*0.016666, scene.latitude, scene.longitude) for time in times]
    beamvals = [0.01 * d for d in dirsol]
    skyvals =  [1 + 0.01 * d for d in difsol]
    sizevals = [beamvals[t]/skyvals[t] for t in range(len(times))]
    values = list(zip(sizevals, beamvals, skyvals))
    sunapply(scene, sun, values, solposs, frames)

def hdrsky(hdrfile, hdrmap, hdrangle, hdrradius):
    hdrangle = '1 {:.3f}'.format(hdrangle * math.pi/180) if hdrangle else '1 0'
    hdrfn = {'0': 'sphere2latlong', '1': 'sphere2angmap'}[hdrmap]
    return("# Sky material\nvoid colorpict hdr_env\n7 red green blue '{}' {}.cal sb_u sb_v\n0\n{}\n\nhdr_env glow env_glow\n0\n0\n4 1 1 1 0\n\nenv_glow bubble sky\n0\n0\n4 0 0 0 {}\n\n".format(hdrfile, hdrfn, hdrangle, hdrradius))
       
def sunposlivi(scene, skynode, frames, sun, stime):
    sun.data.shadow_method, sun.data.shadow_ray_samples, sun.data.sky.use_sky = 'RAY_SHADOW', 8, 1
    if skynode['skynum'] < 3: 
        times = [stime + frame*datetime.timedelta(seconds = 3600*skynode.interval) for frame in range(len(frames))]  
        solposs = [solarPosition(t.timetuple()[7], t.hour + (t.minute)*0.016666, scene.latitude, scene.longitude) for t in times]
        beamvals = [solposs[t][0]/15 for t in range(len(times))] if skynode['skynum'] < 2 else [0 for t in range(len(times))]
        skyvals = beamvals
    elif skynode['skynum'] == 3: 
        times = [datetime.datetime(2015, 3, 20, 12, 0)]
        solposs = [solarPosition(t.timetuple()[7], t.hour + (t.minute)*0.016666, 0, 0) for t in times]
        beamvals = [0 for t in range(len(times))]
        skyvals = [5 for t in range(len(times))]
    shaddict = {'0': 0.01, '1': 2, '2': 5, '3': 5}
    values = list(zip([shaddict[str(skynode['skynum'])] for t in range(len(times))], beamvals, skyvals))
    sunapply(scene, sun, values, solposs, frames)

def sunapply(scene, sun, values, solposs, frames):
    sun.data.animation_data_clear()
    sun.animation_data_clear()
    sun.animation_data_create()
    sun.animation_data.action = bpy.data.actions.new(name="EnVi Sun")
    sunposx = sun.animation_data.action.fcurves.new(data_path="location", index = 0)
    sunposy = sun.animation_data.action.fcurves.new(data_path="location", index = 1)
    sunposz = sun.animation_data.action.fcurves.new(data_path="location", index = 2)
    sunposx.keyframe_points.add(len(frames))
    sunposy.keyframe_points.add(len(frames))
    sunposz.keyframe_points.add(len(frames))
    sunrotx = sun.animation_data.action.fcurves.new(data_path="rotation_euler", index = 0)
    sunroty = sun.animation_data.action.fcurves.new(data_path="rotation_euler", index = 1)
    sunrotz = sun.animation_data.action.fcurves.new(data_path="rotation_euler", index = 2)
    sunrotx.keyframe_points.add(len(frames))
    sunroty.keyframe_points.add(len(frames))
    sunrotz.keyframe_points.add(len(frames))
    sunenergy = sun.animation_data.action.fcurves.new(data_path="energy")
    sunenergy.keyframe_points.add(len(frames))
    
# This is an attempt to use low level routines for node value animation but it don't work.
    if sun.data.node_tree:
        sun.data.node_tree.animation_data_clear()
        sun.data.node_tree.animation_data_create()
        sun.data.node_tree.animation_data.action = bpy.data.actions.new(name="EnVi Sun Node")
        emnodes = [emnode for emnode in sun.data.node_tree.nodes if emnode.bl_label == 'Emission']
        for emnode in emnodes:
            em1 = sun.data.node_tree.animation_data.action.fcurves.new(data_path='nodes["{}"].inputs[1].default_value'.format(emnode.name))
#            em2 = sun.data.node_tree.animation_data.action.fcurves.new(data_path='nodes["{}"].inputs[1].default_value'.format(emnode.name))
            em1.keyframe_points.add(len(frames))
#            em2.keyframe_points.add(len(frames))
        bbnodes = [bbnode for bbnode in sun.data.node_tree.nodes if bbnode.bl_label == 'Blackbody']
        for bbnode in bbnodes:
            bb1 = sun.data.node_tree.animation_data.action.fcurves.new(data_path='nodes["{}"].inputs[0].default_value'.format(bbnode.name))
            bb1.keyframe_points.add(len(frames))
            
    if scene.world.node_tree:
        scene.world.node_tree.animation_data_clear() 
        scene.world.node_tree.animation_data_create()
        scene.world.node_tree.animation_data.action = bpy.data.actions.new(name="EnVi World Node") 
        stnodes = [stnode for stnode in scene.world.node_tree.nodes if stnode.bl_label == 'Sky Texture']
        bnodes = [bnode for bnode in scene.world.node_tree.nodes if bnode.bl_label == 'Background']
        for stnode in stnodes:
            st1x = scene.world.node_tree.animation_data.action.fcurves.new(data_path='nodes["{}"].sun_direction'.format(stnode.name), index = 0)
            st1y = scene.world.node_tree.animation_data.action.fcurves.new(data_path='nodes["{}"].sun_direction'.format(stnode.name), index = 1)
            st1z = scene.world.node_tree.animation_data.action.fcurves.new(data_path='nodes["{}"].sun_direction'.format(stnode.name), index = 2)
            st1x.keyframe_points.add(len(frames))
            st1y.keyframe_points.add(len(frames))
            st1z.keyframe_points.add(len(frames))
        for bnode in bnodes:
            b1 = scene.world.node_tree.animation_data.action.fcurves.new(data_path='nodes["{}"].inputs[1].default_value'.format(bnode.name))
            b1.keyframe_points.add(len(frames))

    for f, frame in enumerate(frames):
        (sun.data.shadow_soft_size, sun.data.energy) = values[f][:2]
        sunpos = [x*20 for x in (-sin(solposs[f][3]), -cos(solposs[f][3]), tan(solposs[f][2]))]
        sunrot = [(pi/2) - solposs[f][2], 0, -solposs[f][3]]
        if scene.render.engine == 'CYCLES' and scene.world.node_tree:
            if 'Sky Texture' in [no.bl_label for no in scene.world.node_tree.nodes]:
                skydir = -sin(solposs[f][3]), -cos(solposs[f][3]), sin(solposs[f][2])
                st1x.keyframe_points[f].co = frame, skydir[0]
                st1y.keyframe_points[f].co = frame, skydir[1]
                st1z.keyframe_points[f].co = frame, skydir[2]
            b1.keyframe_points[f].co = frame, values[f][2]

        if scene.render.engine == 'CYCLES' and sun.data.node_tree:
            for emnode in emnodes:
                em1.keyframe_points[f].co = frame, values[f][1]
        if sun.data.node_tree:
            for bbnode in bbnodes:
                bb1.keyframe_points[f].co = frame, retsunct(solposs[f][2])
                   
        sunposx.keyframe_points[f].co = frame, sunpos[0]
        sunposy.keyframe_points[f].co = frame, sunpos[1]
        sunposz.keyframe_points[f].co = frame, sunpos[2]
        sunrotx.keyframe_points[f].co = frame, sunrot[0]
        sunroty.keyframe_points[f].co = frame, sunrot[1]
        sunrotz.keyframe_points[f].co = frame, sunrot[2]
        sunenergy.keyframe_points[f].co = frame, values[f][1]

    sun.data.cycles.use_multiple_importance_sampling = True

def retsunct(beta):
    return 2500 + 3000*sin(beta)**0.5 if beta > 0 else 2500
    