import bpy
from bpy.types import Operator, AddonPreferences
from bpy.props import StringProperty, BoolProperty
import os
from os import path as osp
import xml.etree.ElementTree as ET
import sys
from mathutils import Matrix

from bpy_extras.io_utils import ExportHelper, orientation_helper
from bpy_extras.io_utils import ImportHelper

class MitsubaFileImport(Operator, ImportHelper):
    """Import from Mitsuba 2 scene"""
    bl_idname = "import_scene.mitsuba2"
    bl_label = "Mitsuba 2 Import"

    bl_obj_keys = {}
    default_dict = {}

    def __init__(self):
        self.prefs = bpy.context.preferences.addons[__package__].preferences
    
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
        if in_str[0] == '$':
            return self.default_dict[in_str[1:]]
        else:
            return in_str

    def parse_transform(self, node):
        from mitsuba.core import Transform4f
        trao = Transform4f()
        for child in node:
            components = [0.0]*3
            if('x' in child.attrib): components[0] = float(self.replace_default(child.attrib['x']))
            if('y' in child.attrib): components[1] = float(self.replace_default(child.attrib['y']))
            if('z' in child.attrib): components[2] = float(self.replace_default(child.attrib['z']))

            # print("components", components)
            # TODO
            if('value' in child.attrib): pass

            if( child.tag == 'translate'):    
                trao = Transform4f.translate(components)*trao
            elif( child.tag == 'scale'):
                trao = Transform4f.scale(components)*trao
            elif( child.tag == 'rotate'):
                angle = float(child.attrib['angle'])
                trao = Transform4f.rotate(components, angle)*trao

        return trao

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
                child.tag != 'default'): continue

            # print("Obtained shape/include/default")
            # parse default
            if(child.tag == 'default'):
                self.default_dict[child.attrib['name']] = child.attrib['value']

            # recursive call
            if(child.tag == 'include'):
                include_fn = self.replace_default(child.attrib['filename'])
                # convert to global filepath
                include_fn = osp.join(dirpath, include_fn)
                self.parse_xml(context, include_fn)

            # print("Parsing shape")
            # parse mesh
            mesh_filename = None
            mesh_transform = None
            for grandchild in child:
                if grandchild.tag == 'string' and grandchild.attrib['name'] == 'filename':
                    mesh_filename = self.replace_default(grandchild.attrib['value'])

                elif grandchild.tag == 'transform':
                    # this doesn't work
                    mesh_transform = self.parse_transform(grandchild)
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
                bpy.ops.import_mesh.ply( filepath=osp.join(dirpath, mesh_filename))
            elif(mesh_type == 'stl'):
                bpy.ops.import_mesh.stl( filepath=osp.join(dirpath, mesh_filename))
            if(mesh_type == 'obj'):
                # TODO check this convention
                bpy.ops.import_scene.obj( filepath=osp.join(dirpath, mesh_filename), \
                    axis_forward='Y', axis_up = 'Z')

            # get the new obj key
            new_key_set = set(context.scene.objects.keys())
            new_key = new_key_set - self.bl_obj_keys
            new_key = list(new_key)[0]
            self.bl_obj_keys = new_key_set

            if mesh_transform is not None:
                new_obj = context.scene.objects[new_key]
                new_obj.matrix_world = Matrix(mesh_transform.matrix.numpy())


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
