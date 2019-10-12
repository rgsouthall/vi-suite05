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

import bpy, bmesh, os, mathutils
from .vi_func import selobj

ofheader = r'''/*--------------------------------*- C++ -*----------------------------------*\
| =========                 |                                                 |
| \\      /  F ield         | OpenFOAM:    The Open Source CFD Toolbox        |
|  \\    /   O peration     | Version:     5                                  |
|   \\  /    A nd           | Web:         www.OpenFOAM.org                   |
|    \\/     M anipulation  | Created by:  FloVi (part of the VI-Suite)       |
\*---------------------------------------------------------------------------*/''' + '\n\n'

flovi_p_bounds = {'icoFoam': {'0': ('zeroGradient', 'fixedValue', 'totalPressure'), '1': ('zeroGradient', 'fixedValue')}, 
                'simpleFoam': {'0': ('zeroGradient', 'fixedValue', 'freestreamPressure', 'totalPressure'), '1': ['zeroGradient'], '2': ('None')},
                'buoyantBoussinesqSimpleFoam':{'0': ('zeroGradient', 'fixedValue', 'freestreamPressure', 'totalPressure'), '1': ['zeroGradient']},
                'buoyantSimpleFoam':{'0': ('zeroGradient', 'fixedValue', 'freestreamPressure', 'totalPressure'), '1': ['zeroGradient']}}

flovi_u_bounds = {'icoFoam': {'0': ('zeroGradient','noSlip', 'fixedValue'), '1': ('zeroGradient', 'noSlip', 'fixedValue')}, 
                'simpleFoam': {'0': ('zeroGradient', 'fixedValue', 'inletOutlet', 'freestream', 'pressureInletOutletVelocity', 'slip'), '1': ('noSlip', 'fixedValue', 'slip'), '2': ('None')},
                'buoyantBoussinesqSimpleFoam': {'0': ('zeroGradient', 'fixedValue', 'inletOutlet', 'freestream', 'pressureInletOutletVelocity', 'slip'), '1': ('noSlip', 'fixedValue', 'slip')},
                'buoyantSimpleFoam': {'0': ('zeroGradient', 'fixedValue', 'inletOutlet', 'freestream', 'pressureInletOutletVelocity', 'slip'), '1': ('noSlip', 'fixedValue', 'slip')}}

flovi_nut_bounds = {'simpleFoam': {'0': ['calculated'], '1': ['nutkWallFunction'], '2': ('None')},
                    'buoyantBoussinesqSimpleFoam': {'0': ['calculated'], '1': ['nutkWallFunction']},
                    'buoyantSimpleFoam': {'0': ['calculated'], '1': ['nutkWallFunction']}}
flovi_nutilda_bounds = {'simpleFoam': {'0': ('zeroGradient', 'fixedValue'), '1': ('zeroGradient', 'fixedValue'), '2': ('None')},
                        'buoyantBoussinesqSimpleFoam': {'0': ('zeroGradient', 'fixedValue'), '1': ('zeroGradient', 'fixedValue')},
                        'buoyantSimpleFoam': {'0': ('zeroGradient', 'fixedValue'), '1': ('zeroGradient', 'fixedValue')}}
flovi_k_bounds = {'simpleFoam': {'0': ('fixedValue', 'inletOutlet'), '1': ['kqRWallFunction'], '2': ('None')},
                'buoyantBoussinesqSimpleFoam': {'0': ('fixedValue', 'inletOutlet'), '1': ['kqRWallFunction']},
                'buoyantSimpleFoam': {'0': ('fixedValue', 'inletOutlet'), '1': ['kqRWallFunction']}}
flovi_epsilon_bounds = {'simpleFoam': {'0': ('fixedValue', 'inletOutlet'), '1': ['epsilonWallFunction'], '2': ('None')},
                        'buoyantBoussinesqSimpleFoam': {'0': ('fixedValue', 'inletOutlet'), '1': ['epsilonWallFunction']},
                        'buoyantSimpleFoam': {'0': ('fixedValue', 'inletOutlet'), '1': ['epsilonWallFunction']}}
flovi_omega_bounds = {'simpleFoam': {'0': ('zeroGradient', 'fixedValue'), '1': ['omegaWallFunction'], '2': ()},
                        'buoyantBoussinesqSimpleFoam': {'0': ('zeroGradient', 'fixedValue'), '1': ['omegaWallFunction']},
                        'buoyantSimpleFoam': {'0': ('zeroGradient', 'fixedValue'), '1': ['omegaWallFunction']}}
flovi_t_bounds = {'buoyantBoussinesqSimpleFoam': {'0': ('zeroGradient', 'fixedValue', 'inletOutlet'), '1': ('zeroGradient', 'fixedValue'), '2': ('None')},
                  'buoyantSimpleFoam': {'0': ('zeroGradient', 'fixedValue', 'inletOutlet'), '1': ('zeroGradient', 'fixedValue')}}
flovi_prgh_bounds = {'buoyantBoussinesqSimpleFoam': {'0': ('fixedFluxPressure', 'prghTotalHydrostaticPressure'), '1': ('fixedFluxPressure', 'fixedValue'), '2': ('None')},
                     'buoyantSimpleFoam': {'0': ('fixedFluxPressure', 'prghTotalHydrostaticPressure'), '1': ('fixedFluxPressure', 'fixedValue')}}
flovi_a_bounds = {'buoyantBoussinesqSimpleFoam': {'0': ('calculated', 'compressible::alphatWallFunction'), '1': ('calculated', 'compressible::alphatWallFunction')},
                'buoyantSimpleFoam': {'0': ('calculated', 'compressible::alphatWallFunction'), '1': ('calculated', 'compressible::alphatWallFunction')}}
#flovi_p_dimens


#ico_p_bounds = {'p': ('zeroGradient', 'fixedValue'), 
#              'U': ('zeroGradient','noSlip', 'fixedValue')}
#ico_w_bounds = {'p': ('zeroGradient', 'fixedValue'), 
#              'U': ('zeroGradient', 'noSlip', 'fixedValue')}
#sim_p_bounds = {'p': ('zeroGradient', 'fixedValue', 'freestreamPressure'), 
#              'U': ('zeroGradient', 'fixedValue', 'inletOutlet', 'freestream', 'pressureInletOutletVelocity', 'slip'),
#              'nut':('nutkWallFunction', 'calculated'),
#              'nuTilda': ('zeroGradient', 'fixedValue'),
#              'k': ('fixedValue', 'inletOutlet'),
#              'epsilon': ('fixedValue', 'inletOutlet'),
#              'omega': ('zeroGradient', 'fixedValue')}
#sim_w_bounds = {'p': ['zeroGradient'], 
#              'U': ('noSlip', 'fixedValue', 'slip'),
#              'nut':('nutkWallFunction'),
#              'nuTilda': ('zeroGradient', 'fixedValue'),
#              'k': ('kqRWallFunction'),
#              'epsilon': ('epsilonWallFunction'),
#              'omega': ('omegaWallFunction')}
#bsim_p_bounds = {'T': ('zeroGradient', 'fixedValue', 'inletOutlet'),
#                'p_rgh': ('fixedFluxPressure', 'prghTotalHydrostaticPressure'),
#                'alphat': ('calculated', 'compressible::alphatWallFunction')}
#bsim_w_bounds = {'T': ('zeroGradient', 'fixedValue'),
#                'p_rgh': ('fixedFluxPressure', 'fixedValue'),
#                'alphat': ('calculated', 'compressible::alphatWallFunction')}
#rbsimbounddict = {'G': 'MarshakRadiation'}
#fvrbsimbounddict = {'IDefault': ('greyDiffusiveRadiation', 'calculated')}

#bound_dict = {'icoFoam': (ico_p_bounds, ico_w_bounds), 'simpleFoam': (sim_p_bounds, sim_w_bounds), 'boussinesc': (bsim_p_bounds, bsim_w_bounds)}

#def ret_fvb_menu(mat, context):
#    return [('{}'.format(b), '{}'.format(b), '{} boundary type'.format(b)) for b in bound_dict[context.scene['flparams']['solver']][int(mat.flovi_bmb_type)]]
# 
def ret_fvbp_menu(mat, context): 
    return [('{}'.format(b), '{}'.format(b), '{} boundary type'.format(b)) for b in flovi_p_bounds[context.scene['flparams']['solver']][mat.flovi_bmb_type]]

def ret_fvbu_menu(mat, context): 
    return [('{}'.format(b), '{}'.format(b), '{} boundary type'.format(b)) for b in flovi_u_bounds[context.scene['flparams']['solver']][mat.flovi_bmb_type]]
           
def ret_fvbnut_menu(mat, context): 
    return [('{}'.format(b), '{}'.format(b), '{} boundary type'.format(b)) for b in flovi_nut_bounds[context.scene['flparams']['solver']][mat.flovi_bmb_type]]

def ret_fvbnutilda_menu(mat, context): 
    return [('{}'.format(b), '{}'.format(b), '{} boundary type'.format(b)) for b in flovi_nutilda_bounds[context.scene['flparams']['solver']][mat.flovi_bmb_type]]    

def ret_fvbk_menu(mat, context): 
    return [('{}'.format(b), '{}'.format(b), '{} boundary type'.format(b)) for b in flovi_k_bounds[context.scene['flparams']['solver']][mat.flovi_bmb_type]] 

def ret_fvbepsilon_menu(mat, context): 
    return [('{}'.format(b), '{}'.format(b), '{} boundary type'.format(b)) for b in flovi_epsilon_bounds[context.scene['flparams']['solver']][mat.flovi_bmb_type]] 

def ret_fvbomega_menu(mat, context): 
    return [('{}'.format(b), '{}'.format(b), '{} boundary type'.format(b)) for b in flovi_omega_bounds[context.scene['flparams']['solver']][mat.flovi_bmb_type]]

def ret_fvbt_menu(mat, context): 
    return [('{}'.format(b), '{}'.format(b), '{} boundary type'.format(b)) for b in flovi_t_bounds[context.scene['flparams']['solver']][mat.flovi_bmb_type]]

def ret_fvba_menu(mat, context): 
    return [('{}'.format(b), '{}'.format(b), '{} boundary type'.format(b)) for b in flovi_a_bounds[context.scene['flparams']['solver']][mat.flovi_bmb_type]]

def ret_fvbprgh_menu(mat, context): 
    return [('{}'.format(b), '{}'.format(b), '{} boundary type'.format(b)) for b in flovi_prgh_bounds[context.scene['flparams']['solver']][mat.flovi_bmb_type]]

def write_header(func):
    def wrapper(o, expnode):
        return ofheader + func(o, expnode)
    return wrapper

def write_ffile(cla, loc, obj):
    location = 'location    "{}";\n'.format(loc) if loc else ''
    return 'FoamFile\n  {{\n    version   2.0;\n    format    ascii;\n    {}    class     {};\n    object    {};\n  }}\n\n'.format(location, cla, obj)

def fvboundwrite(o):
    boundary = ''
    
    for mat in o.data.materials:        
        boundary += "  {}\n  {{\n    type {};\n    faces\n    (\n".format(mat.name, ("patch", "wall", "symmetry", "empty")[int(mat.flovi_bmb_type)])#;\n\n"
        faces = [face for face in o.data.polygons if o.data.materials[face.material_index] == mat]

        for face in faces:
            boundary += "      ("+" ".join([str(v) for v in face.vertices])+")\n"

        boundary += "    );\n  }\n"
    boundary += ");\n\nmergePatchPairs\n(\n);"
    return boundary

#@writeheader    
def fvbmwrite(o, expnode):
    bm = bmesh.new()
    tempmesh = o.to_mesh(scene = bpy.context.scene, apply_modifiers = True, settings = 'PREVIEW')
    bm.from_mesh(tempmesh)
    bm.verts.ensure_lookup_table()
    bm.transform(o.matrix_world)
    bpy.data.meshes.remove(tempmesh)   
    [xs, ys, zs] = [[v.co[i] for v in bm.verts] for i in range(3)]
    bm.transform(mathutils.Matrix.Translation((-min(xs), -min(ys), -min(zs))))
    o['flovi_translate'] = (-min(xs), -min(ys), -min(zs))
    lengths = [mathutils.Vector(v.co).length for v in bm.verts]
    vert0 = bm.verts[lengths.index(min(lengths))]
    angles = [mathutils.Vector(v.co).angle(mathutils.Vector((0, 0, 1))) for v in bm.verts if v != vert0]
#    vert0 = [v for v in bm.verts if v.co[:] == (min(xs), min(ys), min(zs))][0]
    vert4 = bm.verts[angles.index(min(angles)) + 1]
#    print(vert0.index, vert4.index)
#    vert4 = [v for v in bm.verts if (v.co[0], v.co[1]) == (vert0.co[0], vert0.co[1]) and v.co[2] != vert0.co[2]][0]

    for face in bm.faces:
        if vert0 in face.verts and vert4 not in face.verts:
            vis = [vert.index for vert in face.verts][::-1]
            vertorder1 = vis[vis.index(vert0.index):] + vis[:vis.index(vert0.index)]
#            vertorder1 = [vertorder1[0], vertorder1[3], vertorder1[2], vertorder1[1]]
        if vert4 in face.verts and vert0 not in face.verts:
            vis = [vert.index for vert in face.verts]
            vertorder2 = vis[vis.index(vert4.index):] + vis[:vis.index(vert4.index)]
        
    vertorder = ''.join(['{} '.format(v) for v in vertorder1 + vertorder2])

#    omw, bmovs = o.matrix_world, [vert for vert in o.data.vertices]
#    xvec, yvec, zvec = (omw*bmovs[3].co - omw*bmovs[0].co).normalized(), (omw*bmovs[2].co - omw*bmovs[3].co).normalized(), (omw*bmovs[4].co - omw*bmovs[0].co).normalized() 
#    ofvpos = [[(omw*bmov.co - omw*bmovs[0].co)*vec for vec in (xvec, yvec, zvec)] for bmov in bmovs]
#    bmdict = "vertices\n(\n" + "\n".join(["  ({0:.3f} {1:.3f} {2:.3f})" .format(*ofvpo) for ofvpo in ofvpos]) +"\n);\n\n"
    bmdict = "vertices\n(\n" + "\n".join(["  ({0[0]:.3f} {0[1]:.3f} {0[2]:.3f})" .format(v.co) for v in bm.verts]) +"\n);\n\n"
    bmdict += "blocks\n(\n  hex ({}) ({} {} {}) simpleGrading ({} {} {})\n);\n\n".format(vertorder, expnode.bm_xres, expnode.bm_yres, expnode.bm_zres, expnode.bm_xgrad, expnode.bm_ygrad, expnode.bm_zgrad) 
    bmdict += "edges\n(\n);\n\nboundary\n(\n"  
    bmdict += fvboundwrite(o)
    bm.free()
    return ofheader + write_ffile('dictionary', '', 'blockMeshDict') + bmdict
    
def fvblbmgen(mats, ffile, vfile, bfile, meshtype):
    scene = bpy.context.scene
    matfacedict = {mat.name:[0, 0] for mat in mats}
    
    for line in bfile.readlines():
        if line.strip() in matfacedict:
            mat = line.strip()
        elif line.strip() in [o.name for o in bpy.data.objects]:
            mat = bpy.data.objects[line.strip()].data.materials[0].name
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
        bpy.ops.object.add(type='MESH', layers=(False, False, False, False, False, False, 
                                                False, False, False, False, False, False, 
                                                False, False, False, False, False, False, False, True))
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
        bm.verts.new([float(vpos) for vpos in line[1:-2].split(' ')])

    if hasattr(bm.verts, "ensure_lookup_table"):
        bm.verts.ensure_lookup_table()

    for l, line in enumerate([line for line in ffile.readlines() if '(' in line and line[0].isdigit() and len(line.split(' ')) == int(line[0])]):
        newf = bm.faces.new([bm.verts[int(fv)] for fv in line[2:-2].split(' ')])
        
        for facerange in matfacedict.items():
            if l in range(facerange[1][0], facerange[1][0] + facerange[1][1]):
                newf.material_index = matnamedict[facerange[0]]

    bm.transform(o.matrix_world.inverted())
    bm.to_mesh(o.data)
    bm.free()

#def fvbmr(scene, o):
#    points = ''.join(['({} {} {})\n'.format(o.matrix_world * v.co) for v in o.data.verts]) + ')'
#    with open(os.path.join(scene['flparams']['ofcpfilebase'], 'points'), 'r') as pfile:
#        pfile.write(ofheader + write_ffile('vectorField', '"constant/polyMesh"', 'points') + points)
#    faces = ''.join(['({} {} {} {})\n'.format(f.vertices) for f in o.data.faces]) + ')'
#    with open(os.path.join(scene['flparams']['ofcpfilebase'], 'faces'), 'r') as ffile:
#        ffile.write(ofheader + write_ffile('vectorField', '"constant/polyMesh"', 'points') + faces)


def fvmat(self, mn, bound):
#    fvname = on.replace(" ", "_") + self.name.replace(" ", "_") 
    begin = '\n  {}\n  {{\n    type    '.format(mn)  
    end = ';\n  }\n'
    
    if bound == 'p':
        val = 'uniform {}'.format(self.flovi_bmbp_val) if not self.flovi_p_field else '$internalField'
        pdict = {'0': self.flovi_bmbp_subtype, '1': self.flovi_bmbp_subtype, '2': 'symmetry', '3': 'empty'}
        ptdict = {'zeroGradient': 'zeroGradient', 'fixedValue': 'fixedValue;\n    value    {}'.format(val), 'calculated': 'calculated;\n    value    $internalField', 
        'freestreamPressure': 'freestreamPressure', 'totalPressure': 'totalPressure;\n    p0      uniform {};\n    gamma    {};\n    value    {}'.format(self.flovi_bmbp_p0val, self.flovi_bmbp_gamma, val), 'symmetry': 'symmetry', 'empty': 'empty'}
#        if pdict[self.flovi_bmb_type] == 'zeroGradient':
        entry = ptdict[pdict[self.flovi_bmb_type]]            
#        return begin + entry + end 
    
    elif bound == 'U':
        val = 'uniform ({} {} {})'.format(*self.flovi_bmbu_val) if not self.flovi_u_field else '$internalField'
        Udict = {'0': self.flovi_bmbu_subtype, '1': self.flovi_bmbu_subtype, '2': 'symmetry', '3': 'empty'}
        Utdict = {'fixedValue': 'fixedValue;\n    value    {}'.format(val), 'slip': 'slip', 'noSlip': 'noSlip', 'inletOutlet': 'inletOutlet;\n    inletValue    $internalField;\n    value    $internalField',
                  'pressureInletOutletVelocity': 'pressureInletOutletVelocity;\n    value    $internalField', 'zeroGradient': 'zeroGradient', 'symmetry': 'symmetry', 
                  'freestream': 'freestream;\n    freestreamValue    $internalField','calculated': 'calculated;\n    value    $internalField', 'empty': 'empty'}
        entry = Utdict[Udict[self.flovi_bmb_type]]            
#        return begin + entry + end
        
    elif bound == 'nut':
        ndict = {'0': self.flovi_bmbnut_subtype, '1': self.flovi_bmbnut_subtype, '2': 'symmetry', '3': 'empty'}
        ntdict = {'nutkWallFunction': 'nutkWallFunction;\n    value    $internalField', 'nutUSpaldingWallFunction': 'nutUSpaldingWallFunction;\n    value    $internalField', 
        'calculated': 'calculated;\n    value    $internalField', 'inletOutlet': 'inletOutlet;\n    inletValue    $internalField\n    value    $internalField',  'symmetry': 'symmetry','empty': 'empty'}
        entry = ntdict[ndict[self.flovi_bmb_type]]            
#        return begin + entry + end

    elif bound == 'k':
        kdict = {'0': self.flovi_bmbk_subtype, '1': self.flovi_bmbk_subtype, '2': 'symmetry', '3': 'empty'}
        ktdict = {'fixedValue': 'fixedValue;\n    value    $internalField', 'kqRWallFunction': 'kqRWallFunction;\n    value    $internalField', 'inletOutlet': 'inletOutlet;\n    inletValue    $internalField;\n    value    $internalField',
        'calculated': 'calculated;\n    value    $internalField', 'symmetry': 'symmetry', 'empty': 'empty'}
        entry = ktdict[kdict[self.flovi_bmb_type]]            
#        return begin + entry + end

    elif bound == 't':
        val = 'uniform {}'.format(self.flovi_bmbt_val) if not self.flovi_t_field else '$internalField'
        tdict = {'0': self.flovi_bmbt_subtype, '1': self.flovi_bmbt_subtype, '2': 'symmetry', '3': 'empty'}
        ttdict = {'zeroGradient': 'zeroGradient', 'fixedValue': 'fixedValue;\n    value    {}'.format(val), 'inletOutlet': 'inletOutlet;\n    inletValue    $internalField\n    value    $internalField',
        'calculated': 'calculated;\n    value    $internalField', 'symmetry': 'symmetry', 'empty': 'empty'}
        entry = ttdict[tdict[self.flovi_bmb_type]]  
        
    elif bound == 'p_rgh':
        val = 'uniform {}'.format(self.flovi_bmbt_val) if not self.flovi_t_field else '$internalField'
        tdict = {'0': self.flovi_bmbt_subtype, '1': self.flovi_bmbt_subtype, '2': 'symmetry', '3': 'empty'}
        ttdict = {'zeroGradient': 'zeroGradient', 'fixedValue': 'fixedValue;\n    value    {}'.format(val), 'inletOutlet': 'inletOutlet;\n    inletValue    $internalField\n    value    $internalField',
        'calculated': 'calculated;\n    value    $internalField', 'symmetry': 'symmetry', 'empty': 'empty'}
        entry = ttdict[tdict[self.flovi_bmb_type]] 

    elif bound == 'a':
        val = 'uniform {}'.format(self.flovi_bmba_val) if not self.flovi_a_field else '$internalField'
        tdict = {'0': self.flovi_bmba_subtype, '1': self.flovi_bmba_subtype, '2': 'symmetry', '3': 'empty'}
        ttdict = {'zeroGradient': 'zeroGradient', 'fixedValue': 'fixedValue;\n    value    {}'.format(val), 'inletOutlet': 'inletOutlet;\n    inletValue    $internalField\n    value    $internalField',
        'calculated': 'calculated;\n    value    $internalField', 'symmetry': 'symmetry', 'empty': 'empty'}
        entry = ttdict[tdict[self.flovi_bmb_type]] 
        
    elif bound == 'e':
        edict = {'0': self.flovi_bmbe_subtype, '1': self.flovi_bmbe_subtype, '2': 'symmetry', '3': 'empty'}
        etdict = {'symmetry': 'symmetry', 'empty': 'empty', 'inletOutlet': 'inletOutlet;\n    inletValue    $internalField;\n    value    $internalField', 'fixedValue': 'fixedValue;\n    value    $internalField', 
                  'epsilonWallFunction': 'epsilonWallFunction;\n    value    $internalField', 'calculated': 'calculated;\n    value    $internalField', 'symmetry': 'symmetry', 'empty': 'empty'}
        entry = etdict[edict[self.flovi_bmb_type]]            
#        return begin + entry + end
        
    elif bound == 'o':
        odict = {'0': self.flovi_bmbo_subtype, '1': self.flovi_bmbo_subtype, '2': 'symmetry', '3': 'empty'}
        otdict = {'symmetry': 'symmetry', 'empty': 'empty', 'inletOutlet': 'inletOutlet;\n    inletValue    $internalField\n    value    $internalField', 'zeroGradient': 'zeroGradient', 
                  'omegaWallFunction': 'omegaWallFunction;\n    value    $internalField', 'fixedValue': 'fixedValue;\n    value    $internalField'}
        entry = otdict[odict[self.flovi_bmb_type]]            
#        return begin + entry + end
        
    elif bound == 'nutilda':
        ntdict = {'0': self.flovi_bmbnutilda_subtype, '1': self.flovi_bmbnutilda_subtype, '2': 'symmetry', '3': 'empty'}
        nttdict = {'fixedValue': 'fixedValue;\n    value    $internalField', 'inletOutlet': 'inletOutlet;\n    inletValue    $internalField\n    value    $internalField', 'empty': 'empty', 
                   'zeroGradient': 'zeroGradient', 'freestream': 'freestream\n    freeStreamValue  $internalField\n', 'symmetry': 'symmetry'} 
        entry = nttdict[ntdict[self.flovi_bmb_type]]            

    return begin + entry + end
    
def fvvarwrite(scene, obs, node):
    '''Turbulence modelling: k and epsilon required for kEpsilon, k and omega required for kOmega, nutilda required for SpalartAllmaras, nut required for all
        Buoyancy modelling: T''' 
    if node.solver in ('icoFoam', 'simpleFoam', 'buoyantBuosssinesqSimpleFoam'):
        pentry = "dimensions [{} {} {} {} 0 0 0];\ninternalField   uniform {};\n\nboundaryField\n{{\n".format('0', '2', '-2', '0', '{}'.format(node.pnormval))
    else:
        pentry = "dimensions [{} {} {} {} 0 0 0];\ninternalField   uniform {};\n\nboundaryField\n{{\n".format('0', '1', '-1', '0', '{}'.format(node.pabsval))
        
    (Uentry, nutildaentry, nutentry, kentry, eentry, oentry, tentry, p_rghentry, aentry) = ["dimensions [{} {} {} {} 0 0 0];\ninternalField   uniform {};\n\nboundaryField\n{{\n".format(*var) for var in ( 
                                                                                ('0', '1', '-1', '0', '({} {} {})'.format(*node.uval)), 
                                                                                ('0', '2', '-1', '0', '{}'.format(node.nutildaval)), 
                                                                                ('0', '2', '-1', '0', '{}'.format(node.nutval)), 
                                                                                ('0', '2', '-2', '0', '{}'.format(node.kval)), 
                                                                                ('0', '2', '-3', '0', '{}'.format(node.epval)), 
                                                                                ('0', '0', '-1', '0', '{}'.format(node.oval)),
                                                                                ('0', '0', '0', '1', '{}'.format(node.tval)),
                                                                                ('1', '-1', '-2', '0', '{}'.format(node.p_rghval)),
                                                                                ('1', '-1', '-1', '0', '{}'.format(node.aval)))]
    for o in obs:
        for mat in o.data.materials: 
            if o.vi_type == '3':
                matname = '{}_{}'.format(o.name, mat.name) if len(o.data.materials) > 1 else o.name
            elif o.vi_type == '2':
                matname = mat.name 
            if mat.mattype == '2':
                pentry += mat.fvmat(matname, 'p')
                Uentry += mat.fvmat(matname, 'U')
                if node.solver != 'icoFoam':
                    if node.turbulence != 'laminar':
                        nutentry += mat.fvmat(matname, 'nut')                    
                        if node.turbulence ==  'SpalartAllmaras':
                            nutildaentry += mat.fvmat(matname, 'nutilda')
                        elif node.turbulence ==  'kEpsilon':
                            kentry += mat.fvmat(matname, 'k')
                            eentry += mat.fvmat(matname, 'e')
                        elif node.turbulence ==  'kOmega':
                            kentry += mat.fvmat(matname, 'k')
                            oentry += mat.fvmat(matname, 'o')
                    if node.buoyancy or node.radiation:
                        tentry += mat.fvmat(matname, 't')
                        p_rghentry += mat.fvmat(matname, 'p_rgh')
                        aentry += mat.fvmat(matname, 'a')

    pentry += '}'
    Uentry += '}'
    nutentry += '}'
    nutildaentry += '}'
    kentry += '}'
    eentry += '}'
    oentry += '}'
    tentry += '}'
    p_rghentry += '}'
    aentry += '}'
    
    with open(os.path.join(scene['flparams']['of0filebase'], 'p'), 'w') as pfile:
        pfile.write(ofheader + write_ffile('volScalarField', '', 'p') + pentry)
    with open(os.path.join(scene['flparams']['of0filebase'], 'U'), 'w') as Ufile:
        Ufile.write(ofheader + write_ffile('volVectorField', '', 'U') + Uentry)
    if node.solver != 'icoFoam':
        with open(os.path.join(scene['flparams']['of0filebase'], 'nut'), 'w') as nutfile:
            nutfile.write(ofheader + write_ffile('volScalarField', '', 'nuTilda') + nutentry)
        if node.turbulence == 'SpalartAllmaras':
            with open(os.path.join(scene['flparams']['of0filebase'], 'nuTilda'), 'w') as nutildafile:
                nutildafile.write(ofheader + write_ffile('volScalarField', '', 'nut') + nutildaentry)
        if node.turbulence == 'kEpsilon':
            with open(os.path.join(scene['flparams']['of0filebase'], 'k'), 'w') as kfile:
                kfile.write(ofheader + write_ffile('volScalarField', '', 'k') + kentry)
            with open(os.path.join(scene['flparams']['of0filebase'], 'epsilon'), 'w') as efile:
                efile.write(ofheader + write_ffile('volScalarField', '', 'epsilon') + eentry)
        if node.turbulence == 'kOmega':
            with open(os.path.join(scene['flparams']['of0filebase'], 'k'), 'w') as kfile:
                kfile.write(ofheader + write_ffile('volScalarField', '', 'k') + kentry)
            with open(os.path.join(scene['flparams']['of0filebase'], 'omega'), 'w') as ofile:
                ofile.write(ofheader + write_ffile('volScalarField', '', 'omega') + oentry)
        if node.buoyancy or node.radiation:
            with open(os.path.join(scene['flparams']['of0filebase'], 'T'), 'w') as tfile:
                tfile.write(ofheader + write_ffile('volScalarField', '', 'T') + tentry)
            with open(os.path.join(scene['flparams']['of0filebase'], 'alphat'), 'w') as afile:
                afile.write(ofheader + write_ffile('volScalarField', '', 'alphat') + aentry)
            with open(os.path.join(scene['flparams']['of0filebase'], 'p_rgh'), 'w') as prghfile:
                prghfile.write(ofheader + write_ffile('volScalarField', '', 'p_rgh') + p_rghentry)    

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
        'solvers\n{\n  p\n  {\n    solver          GAMG;\n    smoother  GaussSeidel;\n    tolerance       1e-06;\n    relTol          0.1;\n  }\n\n' + \
        '  "(U|k|epsilon|omega|R|nuTilda)"\n  {\n    solver          smoothSolver;\n    smoother        symGaussSeidel;\n    tolerance       1e-05;\n    relTol          0;  \n  }\n}\n\n'
    if node.solver == 'icoFoam':
        ofheader += 'PISO\n{\n  nCorrectors     2;\n  nNonOrthogonalCorrectors 0;\n  pRefCell        0;\n  pRefValue       0;\n}\n\n' + \
        'solvers\n{\n    p\n    {\n        solver          GAMG;\n        tolerance       1e-06;\n        relTol          0.1;\n        smoother        GaussSeidel;\n' + \
        '        nPreSweeps      0;\n        nPostSweeps     2;\n        cacheAgglomeration true;\n        nCellsInCoarsestLevel 10;\n        agglomerator    faceAreaPair;\n'+ \
        '        mergeLevels     1;\n    }\n\npFinal\n{\n    $p;\n    relTol 0;\n}\n\n    U\n    {\n        solver          smoothSolver;\n        smoother        GaussSeidel;\n        nSweeps         2;\n' + \
        '        tolerance       1e-08;\n        relTol          0.1;\n    }\n\n    nuTilda\n    {\n        solver          smoothSolver;\n        smoother        GaussSeidel;\n' + \
        '        nSweeps         2;\n        tolerance       1e-08;\n        relTol          0.1;\n    }\n}\n\n'
    elif node.solver == 'simpleFoam':   
        
        ofheader += 'SIMPLE\n{{\n  nNonOrthogonalCorrectors 0;\n  pRefCell        0;\n  pRefValue       0;\n\n    residualControl\n  {{\n    "(p|U|k|omega|nut|nuTilda)" {};\n    epsilon  {};\n}}\n}}\n'.format(node.convergence, node.econvergence)
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
        if node.turbulence == 'laminar':
            ofheader += 'default         none;\n    div(phi,U)   bounded Gauss upwind;\n    div(phi,k)      bounded Gauss upwind;\n    div(phi,epsilon)  bounded Gauss upwind;\n    div((nuEff*dev2(T(grad(U))))) Gauss linear;\n}\n\n'

        elif node.turbulence == 'kEpsilon':
            ofheader += 'default         none;\n    div(phi,U)   bounded Gauss upwind;\n    div(phi,k)      bounded Gauss upwind;\n    div(phi,epsilon)  bounded Gauss upwind;\n    div((nuEff*dev2(T(grad(U))))) Gauss linear;\n}\n\n'
        elif node.turbulence == 'kOmega':
            ofheader += 'default         none;\n    div(phi,U)   bounded Gauss upwind;\n    div(phi,k)      bounded Gauss upwind;\n    div(phi,omega)  bounded Gauss upwind;\n    div((nuEff*dev2(T(grad(U))))) Gauss linear;\n}\n\n'
        elif node.turbulence == 'SpalartAllmaras':
            ofheader += 'default         none;\n    div(phi,U)   bounded Gauss linearUpwind grad(U);\n    div(phi,nuTilda)      bounded Gauss linearUpwind grad(nuTilda);\n    div((nuEff*dev2(T(grad(U))))) Gauss linear;\n}\n\n'
        ofheader += 'laplacianSchemes\n{\n    default         Gauss linear corrected;\n}\n\n' + \
        'interpolationSchemes\n{\n    default         linear;\n}\n\nsnGradSchemes\n{\n    default         corrected;\n}\n\n' + \
        'fluxRequired\n{\n    default         no;\n    p               ;\n}\n\nwallDist\n{\n    method meshWave;\n}\n\n'
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
    ofheader = 'FoamFile\n{\n    version     2.0;\n    format      ascii;\n    class       dictionary;\n    location    "constant";\n    object      turbulenceProperties;\n}\n\n'
    if turb == 'laminar':
        ofheader += 'simulationType laminar;\n\n'
    else:
        ofheader += 'simulationType RAS;\n\n'
        ofheader += 'RAS\n{{\nRASModel        {};\n\nturbulence      on;\n\nprintCoeffs     on;\n}}\n\n'.format(turb)
    return ofheader

def fvtphwrite():
    ofheader = '''FoamFile
{
    version     2.0;
    format      ascii;
    class       dictionary;
    location    "constant";
    object      thermophysicalProperties;
}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

thermoType
{
    type            heRhoThermo;
    mixture         pureMixture;
    transport       const;
    thermo          hConst;
    equationOfState perfectGas;
    specie          specie;
    energy          sensibleEnthalpy;
}

pRef            100000;

mixture
{
    specie
    {
        molWeight       28.9;
    }
    thermodynamics
    {
        Cp              1000;
        Hf              0;
    }
    transport
    {
        mu              1.8e-05;
        Pr              0.7;
    }
}'''
    return ofheader  

def fvshmlayers(oname, node):
    surfdict = {"0": (("firstLayerThickness", node.frlayer), ("thickness", node.olayer)),
                "1": (("firstLayerThickness", node.frlayer), ("expansionRatio", node.expansion)),
                "2": (("finalLayerThickness", node.fnlayer), ("expansionRatio", node.expansion)),
                "3": (("finalLayerThickness", node.fnlayer), ("thickness", node.olayer)),
                "4": (("thickness", node.olayer), ("expansionRatio", node.expansion))}
    
    
    return 'addLayersControls\n{{\n  relativeSizes true;\n  layers\n  {{\n    "{}.*"\n    {{\n      nSurfaceLayers {};\n    }}\n  }}\n\n'.format(oname, node.layers)
    '  expansionRatio 1.0;\n  finalLayerThickness 0.3;\n  minThickness 0.1;\n  nGrow 0;\n  featureAngle 60;\n  slipFeatureAngle 30;\n  nRelaxIter 3;\n  nSmoothSurfaceNormals 1;\n  nSmoothNormals 3;\n' + \
    '  nSmoothThickness 10;\n  maxFaceThicknessRatio 0.5;\n  maxThicknessToMedialRatio 0.3;\n  minMedianAxisAngle 90;\n  nBufferCellsNoExtrude 0;\n  nLayerIter 50;\n}\n\n'
    
def fvshmwrite(node, fvos, bmo, **kwargs):     
    surfdict = {"0": ("firstLayerThickness", node.frlayer, "thickness", node.olayer),
                "1": ("firstLayerThickness", node.frlayer, "expansionRatio", node.expansion),
                "2": ("finalLayerThickness", node.fnlayer, "expansionRatio", node.expansion),
                "3": ("finalLayerThickness", node.fnlayer, "thickness", node.olayer),
                "4": ("thickness", node.olayer, "expansionRatio", node.expansion)}
    
    layersurf = '({}|{})'.format(kwargs['ground'][0].name, fvos[0].name) if kwargs and kwargs['ground'] else fvos[0].name 
    ofheader = 'FoamFile\n{\n    version     2.0;\n    format      ascii;\n    class       dictionary;\n    object      snappyHexMeshDict;\n}\n\n'
    ofheader += 'castellatedMesh    {};\nsnap    {};\naddLayers    {};\ndebug    {};\n\n'.format('true', 'true', ('false', 'true')[node.layers], 0)
    
    ofheader += 'geometry\n{\n'

    for o in fvos:
        ofheader += '    {0}\n    {{\n        type triSurfaceMesh;\n        file "{0}.obj";\n    \n}}'.format(o.name)

    ofheader += '};\n\n'
    ofheader += 'castellatedMeshControls\n{{\n  maxLocalCells {};\n  maxGlobalCells {};\n  minRefinementCells {};\n  maxLoadUnbalance 0.10;\n  nCellsBetweenLevels {};\n\n'.format(node.lcells, node.gcells, int(node.gcells/100), node.ncellsbl)
    ofheader += '  features\n  (\n'

    for o in fvos:
        ofheader += '    {{\n      file "{}.eMesh";\n      level {};\n    }}\n\n'.format(o.name, o.flovi_fl)

    ofheader += ');\n\n'
    ofheader +='  refinementSurfaces\n  {\n'

    for o in fvos:
        ofheader += '    {}\n    {{\n      level ({} {});\n    }}\n\n  '.format(o.name, o.flovi_slmin, o.flovi_slmax) 

    ofheader += '};\n\n'
    ofheader += '  resolveFeatureAngle 30;\n  refinementRegions\n  {}\n\n'
    ofheader += '  locationInMesh ({0[0]:} {0[1]} {0[2]});\n  allowFreeStandingZoneFaces true;\n}}\n\n'.format(mathutils.Matrix.Translation(bmo['flovi_translate']) * bpy.data.objects[node.empties].location)
    ofheader += 'snapControls\n{\n  nSmoothPatch 3;\n  tolerance 2.0;\n  nSolveIter 30;\n  nRelaxIter 5;\n  nFeatureSnapIter 10;\n  implicitFeatureSnap false;\n  explicitFeatureSnap true;\n  multiRegionFeatureSnap false;\n}\n\n'
    ofheader += 'addLayersControls\n{\n  relativeSizes true;\n  layers\n  {\n'

    for o in fvos:
        ofheader += '"{}.*"\n    {{\n      nSurfaceLayers {};\n    }}\n'.format(o.name, o.flovi_sl)

    ofheader += '}}\n\n'.format(o.name, node.layers)
    ofheader += '  {0[0]} {0[1]};\n  {0[2]} {0[3]};\n  minThickness 0.1;\n  nGrow 0;\n  featureAngle 60;\n  slipFeatureAngle 30;\n  nRelaxIter 5;\n  nSmoothSurfaceNormals 1;\n  nSmoothNormals 3;\n'.format(surfdict[node.layerspec][:]) + \
                '  nSmoothThickness 10;\n  maxFaceThicknessRatio 0.5;\n  maxThicknessToMedialRatio 0.3;\n  minMedianAxisAngle 90;\n  nBufferCellsNoExtrude 0;\n  nLayerIter 50;\n}\n\n'
    ofheader += 'meshQualityControls\n{\n  #include "meshQualityDict"\n  nSmoothScale 4;\n  errorReduction 0.75;\n}\n\n'
    ofheader += 'writeFlags\n(\n  scalarLevels\n  layerSets\n  layerFields\n);\n\nmergeTolerance 1e-6;\n'
    return ofheader


def fvdcpwrite(p):
    body = 'numberOfSubdomains {0};\n\nmethod          simple;\n\nsimpleCoeffs\n{{\n    n               ({0} 1 1);\n    delta           0.001;\n}}\n\nhierarchicalCoeffs\n{{\n    n               (1 1 1);\n    delta           0.001;\n    order           xyz;\n}}\n\nmanualCoeffs\n{{\n    dataFile        "";\n}}\ndistributed     no;\nroots           ( );'.format(p)
    return ofheader + write_ffile("dictionary", "system", "decomposeParDict") + body

#
#numberOfSubdomains 16;
#
#method          simple;
#
#simpleCoeffs
#{
#    n               (4 4 1);
#    delta           0.001;
#}
#
#hierarchicalCoeffs
#{
#    n               (1 1 1);
#    delta           0.001;
#    order           xyz;
#}
#
#manualCoeffs
#{
#    dataFile        "";
#}
#
#distributed     no;
#
#roots           ( );
#
#
#// ************************************************************************* //

def fvmqwrite():
    ofheader = 'FoamFile\n{\n  version     2.0;\n  format      ascii;\n  class       dictionary;\n  object      meshQualityDict;\n}\n\n'
    ofheader += '#include "$WM_PROJECT_DIR/etc/caseDicts/mesh/generation/meshQualityDict"'
    return ofheader
    
def fvsfewrite(fvos):
    ofheader = 'FoamFile\n{\n  version     2.0;\n  format      ascii;\n  class       dictionary;\n  object      surfaceFeatureExtractDict;\n}\n\n'
    for o in fvos:
        ofheader += '{}.obj\n{{\n  extractionMethod    extractFromSurface;\n\n  extractFromSurfaceCoeffs\n  {{\n    includedAngle   150;\n  }}\n\n    writeObj\n    yes;\n}}\n'.format(o.name)
    return ofheader

def fvobjwrite(scene, fvos, bmo):
    objheader = '# FloVi obj exporter\n'
#    bmomw, bmovs = bmo.matrix_world, [vert for vert in bmo.data.vertices]
    for o in fvos:
        with open(os.path.join(scene['flparams']['ofctsfilebase'], '{}.obj'.format(o.name)), 'w') as objfile:
            bm = bmesh.new()
            tempmesh = o.to_mesh(scene = bpy.context.scene, apply_modifiers = True, settings = 'PREVIEW')
            bm.from_mesh(tempmesh)
            bm.transform(o.matrix_world)
            bm.transform(mathutils.Matrix.Translation(bmo['flovi_translate']))
            bpy.data.meshes.remove(tempmesh)
#            omw, ovs = o.matrix_world, [vert for vert in o.data.vertices]
#            xvec, yvec, zvec = (bmomw*bmovs[3].co - bmomw*bmovs[0].co).normalized(), (bmomw*bmovs[2].co - bmomw*bmovs[3].co).normalized(), (bmomw*bmovs[4].co - bmomw*bmovs[0].co).normalized() 
#            ofvpos = [[(omw*ov.co - bmomw*bmovs[0].co)*vec for vec in (xvec, yvec, zvec)] for ov in ovs]
#            bm = bmesh.new()
#            bm.from_mesh(o.data)
#            vcos = ''.join(['v {} {} {}\n'.format(*ofvpo) for ofvpo in ofvpos])    
            vcos =  ''.join(['v {0[0]} {0[1]} {0[2]}\n'.format(v.co) for v in bm.verts])    
            objfile.write(objheader+vcos)
            for m, mat in enumerate(o.data.materials):
                objfile.write('g {}\n'.format(mat.name) + ''.join(['f {} {} {}\n'.format(*[v.index + 1 for v in f.verts]) for f in bmesh.ops.triangulate(bm, faces = bm.faces)['faces'] if f.material_index == m]))
            objfile.write('#{}'.format(len(bm.faces)))
            bm.free()