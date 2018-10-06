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

import bpy, os, math, subprocess, datetime, bmesh, mathutils, shlex
from math import sin, cos, pi
from subprocess import PIPE, Popen, TimeoutExpired
from .vi_func import clearscene, solarPosition, retobjs, radpoints, clearlayers, bmesh2mesh, viparams, ct2RGB, logentry

def radgexport(export_op, node, **kwargs):
    scene = bpy.context.scene
    clearscene(scene, export_op)
    frames = range(node['Options']['fs'], node['Options']['fe'] + 1)
    scene['liparams']['cp'] = node.cpoint
    if bpy.context.active_object and not bpy.context.active_object.layers[scene.active_layer]:
        export_op.report({'INFO'}, "Active geometry is not on the active layer. You may need to lock layers.")
    geooblist, caloblist, lightlist = retobjs('livig'), retobjs('livic'), retobjs('livil')
    scene['liparams']['livig'], scene['liparams']['livic'], scene['liparams']['livil'] = [o.name for o in geooblist], [o.name for o in caloblist], [o.name for o in lightlist]
    eolist = set(geooblist + caloblist)
#    mats = set([item for sublist in [o.data.materials for o in eolist] for item in sublist])
    mats = bpy.data.materials

    for o in eolist:
        if not node.animated:
            o.animation_data_clear()
            o.data.animation_data_clear()
        for k in o.keys():
            del o[k]
        if o in caloblist:
            o['rtpoints'] = {}
            o['lisenseareas'] = {}

    for frame in frames:
        scene.frame_set(frame)
        mradfile =  "".join([m.radmat(scene) for m in mats if m])
        bpy.ops.object.select_all(action='DESELECT')
        tempmatfilename = scene['viparams']['filebase']+".tempmat"
        with open(tempmatfilename, "w") as tempmatfile:
            tempmatfile.write(mradfile)

        # Geometry export routine

        gradfile = "# Geometry \n\n"

        for o in eolist:
#            print([o.name for o in eolist])

#            else:
            bm = bmesh.new()
            tempmesh = o.to_mesh(scene = scene, apply_modifiers = True, settings = 'PREVIEW', calc_undeformed = False)
            bm.from_mesh(tempmesh)
            bm.transform(o.matrix_world)
            bm.normal_update()
            bpy.data.meshes.remove(tempmesh)

            gradfile += bmesh2mesh(scene, bm, o, frame, tempmatfilename, node.fallback)

            if o in caloblist:
                geom = (bm.faces, bm.verts)[int(node.cpoint)]
                if frame == frames[0]:
                    clearlayers(bm, 'a')
                    geom.layers.int.new('cindex')
                    o['cpoint'] = node.cpoint
                geom.layers.string.new('rt{}'.format(frame))
                o.rtpoints(bm, node.offset, str(frame))
                bm.transform(o.matrix_world.inverted())
                bm.to_mesh(o.data)

            bm.free()

            if o.particle_systems:
                ps = o.particle_systems.active
                particles = ps.particles
                dob = ps.settings.dupli_object
                dobs = [dob] if dob else []
                dobs = ps.settings.dupli_group.objects if not dobs else dobs

                for dob in dobs:
                    bm = bmesh.new()
                    tempmesh = dob.to_mesh(scene = scene, apply_modifiers = True, settings = 'PREVIEW', calc_undeformed = False)
                    bm.from_mesh(tempmesh)
                    bm.transform(dob.matrix_world)
                    bm.normal_update()
                    bpy.data.meshes.remove(tempmesh)
                    gradfile += bmesh2mesh(scene, bm, dob, frame, tempmatfilename, node.fallback)
                    bm.free()

                    if os.path.join(scene['viparams']['newdir'], 'obj', '{}-{}.mesh'.format(dob.name.replace(' ', '_'), frame)) in gradfile:
                        for p, part in enumerate(particles):
                            gradfile += 'void mesh id\n17 {6} -t {2[0]:.4f} {2[1]:.4f} {2[2]:.4f} -s {4:.3f} -rx {5[0]:.4f} -ry {5[1]:.4f} -rz {5[2]:.4f} -t {3[0]:.4f} {3[1]:.4f} {3[2]:.4f} \n0\n0\n\n'.format(dob.name,
                                        p, [-p for p in dob.location], part.location, part.size, [180 * r/math.pi for r in part.rotation.to_euler('XYZ')], os.path.join(scene['viparams']['newdir'], 'obj', '{}-{}.mesh'.format(dob.name.replace(' ', '_'), frame)))
                    else:
                        logentry('Radiance mesh export of {} failed. Dupli_objects not exported'.format(dob.name))

    # Lights export routine

        lradfile = "# Lights \n\n"
        for o in lightlist:
            if ' ' in o.ies_name:
                export_op.report({'ERROR'}, 'There is a space in the {} IES file name - rename it'.format(o.name))
            iesname = os.path.splitext(os.path.basename(o.ies_name))[0]

            if os.path.isfile(o.ies_name):
                iescmd = "ies2rad -t default -m {0} -c {1[0]:.3f} {1[1]:.3f} {1[2]:.3f} -p '{2}' -d{3} -o {4}-{5} '{6}'".format(o.ies_strength, (o.ies_rgb, ct2RGB(o.ies_ct))[o.ies_colmenu == '1'], scene['liparams']['lightfilebase'], o.ies_unit, iesname, frame, o.ies_name)
                subprocess.call(shlex.split(iescmd))

                if o.type == 'LAMP':
                    if o.parent:
                        o = o.parent
                    lradfile += u'!xform -rx {0[0]:.3f} -ry {0[1]:.3f} -rz {0[2]:.3f} -t {1[0]:.3f} {1[1]:.3f} {1[2]:.3f} "{2}.rad"\n\n'.format([(180/pi)*o.rotation_euler[i] for i in range(3)], o.location, os.path.join(scene['liparams']['lightfilebase'], iesname+"-{}".format(frame)))

                elif o.type == 'MESH':
                    tm = o.to_mesh(scene = bpy.context.scene, apply_modifiers = True, settings = 'PREVIEW')
                    bm = bmesh.new()
                    bm.from_mesh(tm)
                    bpy.data.meshes.remove(tm)
                    bm.transform(o.matrix_world)
                    bm.normal_update()
                    bm.faces.ensure_lookup_table()
                    for f in bm.faces:
                        lrot = mathutils.Vector.rotation_difference(mathutils.Vector((0, 0, -1)), f.normal).to_euler('XYZ')
                        lradfile += u'!xform -rx {0[0]:.3f} -ry {0[1]:.3f} -rz {0[2]:.3f} -t {1[0]:.3f} {1[1]:.3f} {1[2]:.3f} "{2}"{3}'.format([math.degrees(lr) for lr in lrot], f.calc_center_bounds(), os.path.join(scene['liparams']['lightfilebase'], iesname+"-{}.rad".format(frame)), ('\n', '\n\n')[f == bm.faces[-1]])
                    bm.free()

            elif iesname:
                export_op.report({'ERROR'}, 'The IES file associated with {} cannot be found'.format(o.name))

        sradfile = "# Sky \n\n"
        node['Text'][str(frame)] = mradfile+gradfile+lradfile+sradfile

def livi_sun(scene, node, frame):
    if node.skyprog in ('0', '1') and node.contextmenu == 'Basic':
        simtime = node.starttime + frame*datetime.timedelta(seconds = 3600*node.interval)
        solalt, solazi, beta, phi = solarPosition(simtime.timetuple()[7], simtime.hour + (simtime.minute)*0.016666, scene.latitude, scene.longitude)
        if node.skyprog == '0':
            gsrun = Popen("gensky -ang {} {} {} -t {} -g {}".format(solalt, solazi, node['skytypeparams'], node.turb, node.gref).split(), stdout = PIPE)
        else:
            gsrun = Popen("gendaylit -ang {} {} {} -g {}".format(solalt, solazi, node['skytypeparams'], node.gref).split(), stdout = PIPE)
    else:
        gsrun = Popen("gensky -ang {} {} {} -g {}".format(45, 0, node['skytypeparams'], node.gref).split(), stdout = PIPE)
    return gsrun.stdout.read().decode()

def hdrexport(scene, f, frame, node, skytext):
    with open('{}-{}sky.oct'.format(scene['viparams']['filebase'], frame), 'w') as skyoct:
        Popen('oconv -w -'.split(), stdin = PIPE, stdout = skyoct).communicate(input = skytext.encode('utf-8'))
    with open(os.path.join(scene['viparams']['newdir'], str(frame)+".hdr"), 'w') as hdrfile:
        rpictcmd = "rpict -vta -vp 0 0 0 -vd 0 1 0 -vu 0 0 1 -vh 360 -vv 360 -x 1500 -y 1500 {}-{}sky.oct".format(scene['viparams']['filebase'], frame)
        Popen(rpictcmd.split(), stdout = hdrfile).communicate()
    cntrun = Popen('cnt 750 1500'.split(), stdout = PIPE)
    rcalccmd = 'rcalc -f {} -e XD=1500;YD=750;inXD=0.000666;inYD=0.001333'.format(os.path.join(scene.vipath, 'Radfiles', 'lib', 'latlong.cal'))
    rcalcrun = Popen(rcalccmd.split(), stdin = cntrun.stdout, stdout = PIPE)
    rtracecmd = 'rtrace -n {} -x 1500 -y 750 -fac {}-{}sky.oct'.format(scene['viparams']['nproc'], scene['viparams']['filebase'], frame)
    with open('{}p.hdr'.format(os.path.join(scene['viparams']['newdir'], str(frame))), 'w') as hdrim:
        Popen(rtracecmd.split(), stdin = rcalcrun.stdout, stdout = hdrim).communicate()
    if '{}p.hdr'.format(frame) not in bpy.data.images:
        bpy.data.images.load(os.path.join(scene['viparams']['newdir'], "{}p.hdr".format(frame)))
    else:
        bpy.data.images['{}p.hdr'.format(frame)].reload()

def livi_sky(sn):
    skytext = "4 .8 .8 1 0\n\n" if sn < 3 else "4 1 1 1 0\n\n"
    return "\nskyfunc glow sky_glow\n0\n0\n" + skytext + "sky_glow source sky\n0\n0\n4 0 0 1  180\n\n"

def livi_ground(r, g, b, ref):
    fac = ref/(r * 0.265 + g * 0.670 + b * 0.065)
    if ref:
        return "skyfunc glow ground_glow\n0\n0\n4 {0[0]:.3f} {0[1]:.3f} {0[2]:.3f} 0\n\nground_glow source ground\n0\n0\n4 0 0 -1 180\n\n".format([c*fac for c in (r, g, b)])
    else:
        return ''

def createradfile(scene, frame, export_op, simnode):
    radtext = ''
    links = (list(simnode.inputs['Geometry in'].links[:]) + list(simnode.inputs['Context in'].links[:]))

    for link in links:
        if str(frame) in link.from_node['Text']:
            radtext += link.from_node['Text'][str(frame)]
        elif frame < min([int(k) for k in link.from_node['Text'].keys()]):
            radtext += link.from_node['Text'][str(min([int(k) for k in link.from_node['Text'].keys()]))]
        elif frame > max([int(k) for k in link.from_node['Text'].keys()]):
            radtext += link.from_node['Text'][str(max([int(k) for k in link.from_node['Text'].keys()]))]

    simnode['radfiles'][str(frame)] = radtext

def createoconv(scene, frame, sim_op, simnode, **kwargs):
    fbase = "{0}-{1}".format(scene['viparams']['filebase'], frame)

    with open("{}.oct".format(fbase), "wb") as octfile:
        try:
            ocrun =  Popen("oconv -w -".split(), stdin = PIPE, stderr = PIPE, stdout = octfile, universal_newlines=True)
            err = ocrun.communicate(input = simnode['radfiles'][str(frame)], timeout = 60)[1]

            if err:
                logentry('Oconv conversion error: {}'.format(err))
                return 'CANCELLED'

        except TimeoutExpired:
            ocrun.kill()
            errmsg = 'Oconv conversion taking too long. Try joining/simplfying geometry or using geometry export fallback'
            sim_op.report({'ERROR'}, errmsg)
            logentry('Oconv error: {}'.format(errmsg))
            return 'CANCELLED'

    for line in err:
        logentry('Oconv error: {}'.format(line))
    if err and 'fatal -' in err:
        sim_op.report({'ERROR'}, 'Oconv conversion failure: {}'.format(err))
        return 'CANCELLED'
    elif err and 'set overflow' in err:
        sim_op.report({'ERROR'}, 'Ratio of largest to smallest geometry is too large. Clean up mesh geometry or decrease the radius of any HDR panorama')
        return 'CANCELLED'

def spfc(self):
    scene = bpy.context.scene
    if not scene['viparams'].get('newframe'):
        scene['viparams']['newframe'] = 1
    else:
        scene['viparams']['newframe'] = 0
        scene.frame_set(scene.frame_current)

    if scene['viparams']['resnode'] == 'VI Sun Path':
        spoblist = {ob.get('VIType'):ob for ob in scene.objects if ob.get('VIType') in ('Sun', 'SPathMesh')}
        beta, phi = solarPosition(scene.solday, scene.solhour, scene.latitude, scene.longitude)[2:]

        if scene.world.use_nodes == False:
            scene.world.use_nodes = True
        nt = bpy.data.worlds[0].node_tree

        if nt and nt.nodes.get('Sky Texture'):
            scene.world.node_tree.nodes['Sky Texture'].sun_direction = -sin(phi), -cos(phi), sin(beta)

        for ob in scene.objects:
            if ob.get('VIType') == 'Sun':
                ob.rotation_euler = pi * 0.5 - beta, 0, -phi
                ob.location.z = spoblist['SPathMesh'].location.z + 100 * sin(beta)
                ob.location.x = spoblist['SPathMesh'].location.x -(100**2 - (spoblist['Sun'].location.z-spoblist['SPathMesh'].location.z)**2)**0.5 * sin(phi)
                ob.location.y = spoblist['SPathMesh'].location.y -(100**2 - (spoblist['Sun'].location.z-spoblist['SPathMesh'].location.z)**2)**0.5 * cos(phi)

                if ob.data.node_tree:
                    for blnode in [blnode for blnode in ob.data.node_tree.nodes if blnode.bl_label == 'Blackbody']:
                        blnode.inputs[0].default_value = 2500 + 3000*sin(beta)**0.5
                    for emnode in [emnode for emnode in ob.data.node_tree.nodes if emnode.bl_label == 'Emission']:
                        emnode.inputs[1].default_value = 10 * sin(beta)

            elif ob.get('VIType') == 'SkyMesh':
                ont = ob.data.materials['SkyMesh'].node_tree
                if ont and ont.nodes.get('Sky Texture'):
                    ont.nodes['Sky Texture'].sun_direction = sin(phi), -cos(phi), sin(beta)

            elif ob.get('VIType') == 'SunMesh':
                ob.location = (0, 0, 0)
                if ob.data.materials[0].node_tree:
                    for smblnode in [smblnode for smblnode in ob.data.materials[0].node_tree.nodes if ob.data.materials and smblnode.bl_label == 'Blackbody']:
                        smblnode.inputs[0].default_value = 2500 + 3000*sin(beta)**0.5
    else:
        return

def cyfc1(self):
    scene = bpy.context.scene
    if 'LiVi' in scene['viparams']['resnode'] or 'Shadow' in scene['viparams']['resnode']:
        for material in [m for m in bpy.data.materials if m.use_nodes and m.mattype == '1']:
            try:
                if any([node.bl_label == 'Attribute' for node in material.node_tree.nodes]):
                    material.node_tree.nodes["Attribute"].attribute_name = str(scene.frame_current)
            except Exception as e:
                print(e, 'Something wrong with changing the material attribute name')

def genbsdf(scene, export_op, o):
    if viparams(export_op, scene):
        return

    bsdfmats = [mat for mat in o.data.materials if mat.radmatmenu == '8']

    if bsdfmats:
        mat = bsdfmats[0]
        mat['bsdf'] = {}
    else:
        export_op.report({'ERROR'}, '{} does not have a BSDF material attached'.format(o.name))

    tm = o.to_mesh(scene = scene, apply_modifiers = True, settings = 'PREVIEW')
    bm = bmesh.new()
    bm.from_mesh(tm)
    bpy.data.meshes.remove(tm)
    bm.transform(o.matrix_world)
    bm.normal_update()
    bsdffaces = [face for face in bm.faces if o.data.materials[face.material_index].radmatmenu == '8']

    if bsdffaces:
        fvec = bsdffaces[0].normal
        mat['bsdf']['normal'] = '{0[0]:.4f} {0[1]:.4f} {0[2]:.4f}'.format(fvec)
    else:
        export_op.report({'ERROR'}, '{} does not have a BSDF material associated with any faces'.format(o.name))
        return

    zvec, xvec = mathutils.Vector((0, 0, 1)), mathutils.Vector((1, 0, 0))
    svec = mathutils.Vector.cross(fvec, zvec)
    bm.faces.ensure_lookup_table()
    bsdfrotz = mathutils.Matrix.Rotation(mathutils.Vector.angle(fvec, zvec), 4, svec)
    bm.transform(bsdfrotz)
    bsdfrotx = mathutils.Matrix.Rotation(math.pi + mathutils.Vector.angle_signed(mathutils.Vector(xvec[:2]), mathutils.Vector(svec[:2])), 4, zvec)#mathutils.Vector.cross(svec, xvec))
    bm.transform(bsdfrotx)
    vposis = list(zip(*[v.co[:] for v in bm.verts]))
    (maxx, maxy, maxz) = [max(p) for p in vposis]
    (minx, miny, minz) = [min(p) for p in vposis]
    bsdftrans = mathutils.Matrix.Translation(mathutils.Vector((-(maxx + minx)/2, -(maxy + miny)/2, -maxz)))
    bm.transform(bsdftrans)
    mradfile = ''.join([m.radmat(scene) for m in o.data.materials if m.radmatmenu != '8'])
    gradfile = radpoints(o, [face for face in bm.faces if o.data.materials and face.material_index < len(o.data.materials) and o.data.materials[face.material_index].radmatmenu != '8'], 0)
    bm.free()
    bsdfsamp = o.li_bsdf_ksamp if o.li_bsdf_tensor == ' ' else 2**(int(o.li_bsdf_res) * 2) * int(o.li_bsdf_tsamp)
    gbcmd = "genBSDF +geom meter -r '{}' {} {} -c {} {} -n {}".format(o.li_bsdf_rcparam,  o.li_bsdf_tensor, (o.li_bsdf_res, ' ')[o.li_bsdf_tensor == ' '], bsdfsamp, o.li_bsdf_direc, scene['viparams']['nproc'])
    mat['bsdf']['xml'] = Popen(shlex.split(gbcmd), stdin = PIPE, stdout = PIPE).communicate(input = (mradfile+gradfile).encode('utf-8'))[0].decode()
    scene['viparams']['vidisp'] = 'bsdf'
    mat['bsdf']['type'] = o.li_bsdf_tensor
