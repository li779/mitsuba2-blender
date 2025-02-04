import bpy
from bpy.types import Operator, AddonPreferences
from bpy.props import StringProperty, BoolProperty
import os
from os import path as osp
import xml.etree.ElementTree as ET
import sys
from mathutils import Matrix
import numpy as np

from bpy_extras.io_utils import ExportHelper, orientation_helper
from bpy_extras.io_utils import ImportHelper, axis_conversion

from ipdb import set_trace

class MitsubaFileImport(Operator, ImportHelper):
    """Import from Mitsuba 2 scene"""
    bl_idname = "import_scene.mitsuba2"
    bl_label = "Mitsuba 2 Import"

    bl_obj_keys = {}
    default_dict = {}

    def __init__(self):
        self.prefs = bpy.context.preferences.addons[__package__].preferences
        # TODO expose params
        self.axis_forward = '-Z'
        self.axis_up = 'Y'
        self.axis_mat_t = axis_conversion(
                to_forward=self.axis_forward,
                to_up=self.axis_up,
            ).to_4x4()
        self.axis_mat_t.transpose()


    def set_path(self, mts_build):
        '''
        Set the different variables necessary to run the addon properly.
        Add the path to mitsuba binaries to the PATH env var.
        Append the path to the python libs to sys.path

        Params
        ------

        mts_build: Path to mitsuba 2 build folder.
        '''
        os.environ['PATH'] += os.pathsep + os.path.join(mts_build, 'dist')
        sys.path.append(os.path.join(mts_build, 'dist', 'python'))

    def replace_default(self, in_str):
        # check for $ in parts of input string
        idx = in_str.find('$')
        if idx>-1:
            untouched_part = in_str[:idx]
            # only replace before ext
            base, ext = osp.splitext(in_str[idx+1:])
            return untouched_part + self.default_dict[base] + ext
        else:
            return in_str

    def untransform_matrix(self, matrix):
        mat = self.axis_mat_t @ matrix
        return mat

    # some cases unaccounted for
    def parse_transform(self, node):
        from mitsuba.core import Transform4f
        trao = Transform4f()
        for child in node:
            if (child.tag == 'translate' or child.tag == 'rotate'):
                components = [0.0]*3
            elif (child.tag == "scale"):
                components = [1.0]*3
            if('x' in child.attrib): components[0] = float(self.replace_default(child.attrib['x']))
            if('y' in child.attrib): components[1] = float(self.replace_default(child.attrib['y']))
            if('z' in child.attrib): components[2] = float(self.replace_default(child.attrib['z']))
            if('value' in child.attrib and child.tag in ['scale', 'translate', 'rotate']): 
                value = float(self.replace_default(child.attrib['value']))
                components = [value]*3

            # print("components", components)
            if( child.tag == 'translate'):    
                trao = Transform4f.translate(components)*trao
            elif( child.tag == 'scale'):
                trao = Transform4f.scale(components)*trao
            elif( child.tag == 'rotate'):
                angle = float(self.replace_default(child.attrib['angle']))
                trao = Transform4f.rotate(components, angle)*trao
            elif(child.tag == "matrix"):
                mat = child.attrib["value"]
                local_trao = np.array([float(val) for val in mat.split()])
                local_trao = np.reshape(local_trao, (4,4))
                trao = Transform4f(local_trao.tolist())*trao

        return trao

    def parse_film(self, context, xml):
        for child in xml:
            if(child.tag=="integer"):
                name = child.attrib["name"]
                if(name == "width"):
                    width = int(self.replace_default(child.attrib["value"]))
                    context.scene.render.resolution_x = width
                elif(name == "height"):
                    height = int(self.replace_default(child.attrib["value"]))
                    context.scene.render.resolution_y = height

    def parse_sensor(self, context, xml):
        location = np.array([0.0]*3)
        rotation = np.array([1.0]*3)
        scale = np.array([1.0]*3)
        fov = 39.6 #deg
        near_clip = 0.001
        far_clip = 1000
        for child in xml:
            # parse transform
            if(child.tag == "transform"):
                sensor_transform = self.parse_transform(child)
                # set_trace()
                init_rot = Matrix.Rotation(np.pi, 4, 'Y')
                init_rot.transpose()
                # print(init_rot)
                sensor_transform = Matrix(sensor_transform.matrix.numpy())
                # print("before", sensor_transform)
                sensor_transform = sensor_transform @ init_rot

                sensor_transform = self.untransform_matrix(sensor_transform)
                print("after", sensor_transform)

                location = sensor_transform.translation
                rotation = sensor_transform.to_euler()
                scale = sensor_transform.to_scale()
            elif(child.tag == "film"):
                self.parse_film(context, child)
            elif(child.tag == "float" and "fov" == child.attrib["name"]):
                fov = float(self.replace_default(child.attrib['value']))
            elif(child.tag == "float" and "nearClip" == child.attrib["name"]):
                near_clip = float(self.replace_default(child.attrib['value']))
            elif(child.tag == "float" and "farClip" == child.attrib["name"]):
                far_clip = float(self.replace_default(child.attrib['value']))

        bpy.ops.object.camera_add(enter_editmode=False, align='WORLD', location=location, rotation=rotation, scale=scale)
        # assumption : last camera is the latest cam
        cam = bpy.data.cameras[-1]
        cam.angle_x =  fov * np.pi/180
        cam.clip_start = near_clip
        cam.clip_end = far_clip

    def parse_xml(self, context, filepath):
        print("Parsing %s"%filepath)
        dirpath = osp.dirname(self.filepath)
        # load xml and only parse shapes
        xml_tree = ET.parse(filepath)
        xml_root = xml_tree.getroot()

        for child in xml_root:
            # print("Current tag %s", child.tag)
            if(child.tag != 'shape' and \
                child.tag != 'include' and \
                child.tag != 'sensor' and \
                child.tag != 'default'): continue

            # print("Obtained shape/include/default")
            # parse default
            if(child.tag == 'default'):
                self.default_dict[child.attrib['name']] = self.replace_default(child.attrib['value'])

            # parse camera
            elif(child.tag == 'sensor' and child.attrib["type"] == "perspective"):
                self.parse_sensor(context, child)
                continue

            # recursive call
            elif(child.tag == 'include'):
                include_fn = self.replace_default(child.attrib['filename'])
                print("include calls", child.attrib["filename"], include_fn, self.default_dict)
                
                # convert to global filepath
                include_fn = osp.join(dirpath, include_fn)
                self.parse_xml(context, include_fn)

            else:
                # print("Parsing shape")
                # parse mesh
                mesh_filename = None
                mesh_transform = None
                for grandchild in child:
                    if grandchild.tag == 'string' and grandchild.attrib['name'] == 'filename':
                        mesh_filename = self.replace_default(grandchild.attrib['value'])

                    elif grandchild.tag == 'transform':
                        mesh_transform = self.parse_transform(grandchild).matrix.numpy()
                        if mesh_transform.ndim == 3:
                            mesh_transform = mesh_transform[0]
                        mesh_transform = Matrix(mesh_transform)
                        mesh_transform = self.untransform_matrix(mesh_transform)
                        # print(mesh_transform)
                        # this doesn't work
                        # load_xml = ET.tostring(grandchild, encoding='unicode')
                        # # get from mitsuba py module
                        # load_xml = """<scene version="2.1.0">
                        #             {}
                        #         </scene>""".format(load_xml)
                        
                        # print("xml string %s"%load_xml)
                        # # load transform using mitsuba
                        # from mitsuba.core import xml
                        # mesh_transform = xml.load_string(load_xml)

                
                print("Importing %s"%mesh_filename)
                if mesh_filename is None:
                    continue

                mesh_type = child.attrib['type']
                if(mesh_type == 'ply'):
                    bpy.ops.import_mesh.ply( filepath=osp.join(dirpath, mesh_filename), \
                        axis_forward='Y', axis_up = 'Z')
                elif(mesh_type == 'stl'):
                    bpy.ops.import_mesh.stl( filepath=osp.join(dirpath, mesh_filename), \
                        axis_forward='-Z', axis_up = 'Y')
                if(mesh_type == 'obj'):
                    # TODO check this convention
                    bpy.ops.import_scene.obj( filepath=osp.join(dirpath, mesh_filename), \
                        axis_forward='-Z', axis_up = 'Y')

                # get the new obj key
                # new_key_set = set(context.scene.objects.keys())
                # new_key = new_key_set - self.bl_obj_keys
                # new_key = list(new_key)[0]
                # self.bl_obj_keys = new_key_set

                if mesh_transform is not None:
                    # new_obj = context.scene.objects[new_key]
                    new_obj = context.object
                    print(mesh_transform)
                    new_obj.matrix_world = mesh_transform


    def execute(self, context):
        # set path to mitsuba
        self.set_path(bpy.path.abspath(self.prefs.mitsuba_path))
        # Make sure we can load mitsuba from blender
        try:
            import mitsuba
            mitsuba.set_variant('scalar_rgb')
        except ModuleNotFoundError:
            self.report({'ERROR'}, "Importing Mitsuba failed. Please verify the path to the library in the addon preferences.")
            return {'CANCELLED'}

        print(context.scene.cursor.matrix, context.scene.cursor.location)

        self.bl_obj_keys = set(context.scene.objects.keys())
        self.scene_origin = context.scene.cursor.matrix
        # send global location
        self.parse_xml(context, self.filepath)        
        return {'FINISHED'}
