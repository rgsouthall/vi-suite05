import bpy, mathutils, math
from .vi_func import clearanim, livisimacc, selobj, gentarget, bres, framerange
from .livi_export import radgexport

def vigen(calc_op, li_calc, resapply, geonode, connode, simnode, geogennode, tarnode):
    scene = bpy.context.scene 
    livioc = scene['liparams']['livic']
    simnode['Animation'] = 'Animated'
    if not scene['liparams']['livim']:
        calc_op.report({'ERROR'}, "No object has been set-up for generative manipulation")
        return
    else:
        liviom = scene['liparams']['livim']
            
    clearanim(scene, [bpy.data.objects[on] for on in scene['liparams']['livim']])    
    scene.frame_set(scene.frame_start)                    
    radgexport(calc_op, geonode, genframe = scene.frame_current)
    res = [li_calc(calc_op, simnode, connode, geonode, livisimacc(simnode, connode), genframe = scene.frame_current)]

    for o in [bpy.data.objects[on] for on in scene['liparams']['livic']]:                         
        if o.name in scene['liparams']['livic']:
            selobj(scene, o)
            o.keyframe_insert(data_path='["licalc"]')
            o.keyframe_insert(data_path='["licalc"]', frame = scene.frame_current + 1)
        else:
            scene['liparams']['livim'].remove(o.name)
        
        if not gentarget(tarnode, bres(scene, o)):
            scene['liparams']['livic'].remove(o.name)
    
    for o in [bpy.data.objects[on] for on in scene['liparams']['livim']]:
        if o.manip == 1 and geogennode.geomenu == 'Mesh':  
            selobj(scene, o)
            bpy.ops.object.shape_key_add(from_mix = False)        
    
    while scene.frame_current < scene.frame_start + geogennode.steps + 1 and scene['liparams']['livic']:        
        if scene.frame_current == scene.frame_start + 1 and geogennode.geomenu == 'Mesh':            
            for o in [bpy.data.objects[on] for on in scene['liparams']['livim']]:  
                selobj(scene, o)
                for face in o.data.polygons:
                    try:
                        face.select = True if all([o.data.vertices[v].groups[o['vgi']] for v in face.vertices]) else False
                    except:
                        face.select = False

                if geogennode.mmanmenu == '3': 
                    bpy.ops.object.mode_set(mode = 'EDIT')                    
                    bpy.ops.mesh.extrude_faces_move(MESH_OT_extrude_faces_indiv={"mirror":False}, TRANSFORM_OT_shrink_fatten={"value":0})
                    if o.vertex_groups.get('genexfaces'):
                        while len(o.vertex_groups) > 1:
                            o.vertex_groups.active_index = 1
                            bpy.ops.object.vertex_group_remove()
                    o.vertex_groups.new('genexfaces')
                    bpy.context.object.vertex_groups.active_index  = 1
                    bpy.ops.object.vertex_group_assign()
                    bpy.ops.object.mode_set(mode = 'OBJECT')                            
                    o['vgi'] = o.vertex_groups['genexfaces'].index
                            
        if scene.frame_current > scene.frame_start:              
            for o in [bpy.data.objects[on] for on in liviom]:
                o.keyframe_insert(data_path='["licalc"]')
                selobj(scene, o)  
                if o.name in scene['liparams']['livim'] and geogennode.geomenu == 'Mesh':
                    bpy.ops.object.shape_key_add(from_mix = False)
                    o.active_shape_key.name = 'gen-' + str(scene.frame_current)
                    modgeo(o, geogennode, scene, scene.frame_current, scene.frame_start)   
                    for shape in o.data.shape_keys.key_blocks:
                        if "Basis" not in shape.name:
                            shape.value = 1 if shape.name == 'gen-{}'.format(scene.frame_current) else 0
                            shape.keyframe_insert("value")                
                elif o.manip == 1 and geogennode.geomenu == 'Object':
                    modgeo(o, geogennode, scene, scene.frame_current, scene.frame_start)
                    o.keyframe_insert(('location', 'rotation_euler', 'scale')[int(geogennode.omanmenu)])
                                        
            radgexport(calc_op, geonode, genframe = scene.frame_current, mo = [bpy.data.objects[on] for on in scene['liparams']['livim']])
            res.append(li_calc(calc_op, simnode, connode, geonode, livisimacc(simnode, connode), genframe = scene.frame_current))
            
            for o in [bpy.data.objects[on] for on in scene['liparams']['livic']]:
                if not gentarget(tarnode, bres(scene, o)):
                    scene['liparams']['livic'] = scene['liparams']['livic'].remove(o.name) if scene['liparams']['livic'].remove(o.name) else []
                    
                    if o.name in scene['liparams']['livim']:
                        scene['liparams']['livim'] = scene['liparams']['livim'].remove(o.name) if scene['liparams']['livim'].remove(o.name) else []
                o.keyframe_insert(data_path='["licalc"]', frame = scene.frame_current + 1)

        scene.frame_end = scene.frame_current + 1                        
        scene.frame_set(scene.frame_current + 1)
            
    scene.frame_end = scene.frame_end - 1  
    scene.fs = scene.frame_start    
        
    for frame in framerange(scene, 'Animation'):
        scene.frame_set(frame)
        for o in [bpy.data.objects[on] for on in liviom]:
            if geogennode.geomenu == 'Mesh' and o.data.shape_keys:
                for shape in o.data.shape_keys.key_blocks:
                    if "Basis" not in shape.name:
                        shape.value = 1 if shape.name == 'gen-{}'.format(frame) else 0
                        if shape == o.data.shape_keys.key_blocks[-1] and frame > int(shape.name.split('-')[1]):
                            shape.value = 1
                        shape.keyframe_insert("value")
                               
    scene.frame_current = scene.frame_start 
    scene['liparams']['livic'] = livioc      
        
def modgeo(o, geogennode, scene, fc, fs):            
    if geogennode.geomenu == 'Object':
        direc = (geogennode.x, geogennode.y, geogennode.z)
        if geogennode.omanmenu == '0':
            if fc == fs + 1:
                o.keyframe_insert('location', frame = fs)
            o.location += mathutils.Vector([(geogennode.extent/geogennode.steps) * xyz for xyz in direc])
            o.keyframe_insert('location', frame = fc)
        if geogennode.omanmenu == '1':
            if fc == fs + 1:
                o.keyframe_insert('rotation_euler', frame = fs)
            o.rotation_euler[0] += ((math.pi/180)*geogennode.extent/geogennode.steps) * direc[0]
            o.rotation_euler[1] += ((math.pi/180)*geogennode.extent/geogennode.steps) * direc[1]
            o.rotation_euler[2] += ((math.pi/180)*geogennode.extent/geogennode.steps) * direc[2]
            o.keyframe_insert('rotation_euler', frame = fc)
        if geogennode.omanmenu == '2':
            if fc == fs + 1:
                o.keyframe_insert('scale', frame = fs)
            o.scale += mathutils.Vector([(geogennode.extent/geogennode.steps) * xyz for xyz in direc])
            o.keyframe_insert('scale', frame = fc)
    else: 
        omw = o.matrix_world
        if fc > fs:
            for face in o.data.polygons:                
                if all([o.data.vertices[v].groups and o.data.vertices[v].groups[o['vgi']] for v in face.vertices]):
                    direc = [1- face.normal.normalized()[i] for i in range(3)] if geogennode.normal else (geogennode.x, geogennode.y, geogennode.z)
                    fcent = tuple(face.center)
                    for v in face.vertices:
                        if geogennode.mmanmenu in ('0', '3'):
                            o.data.shape_keys.key_blocks['gen-{}'.format(fc)].data[v].co = omw.inverted() * mathutils.Vector([(omw * o.data.shape_keys.key_blocks['gen-{}'.format(fc)].data[v].co)[i] + ((fc-fs) * (geogennode.extent/geogennode.steps) * direc[i]) for i in range(3)]) 
                        elif geogennode.mmanmenu == '1':
                            mat_rot = mathutils.Matrix.Rotation(math.radians((fc-fs) * geogennode.extent/geogennode.steps), 4, face.normal)  if geogennode.normal else mathutils.Matrix.Rotation(math.radians((fc-fs) * geogennode.extent/geogennode.steps), 4, mathutils.Vector((geogennode.x, geogennode.y, geogennode.z)))
                            o.data.shape_keys.key_blocks['gen-{}'.format(fc)].data[v].co = (mat_rot * (o.data.shape_keys.key_blocks['Basis'].data[v].co - mathutils.Vector(fcent))) + mathutils.Vector(fcent)
                        elif geogennode.mmanmenu == '2':                            
                            o.data.shape_keys.key_blocks['gen-{}'.format(fc)].data[v].co = [o.data.shape_keys.key_blocks['gen-{}'.format(fc)].data[v].co[i] + (geogennode.extent - 1)/geogennode.steps * (o.data.shape_keys.key_blocks['Basis'].data[v].co[i] - fcent[i]) * direc[i] * (fc-fs)  for i in range(3)]
     
