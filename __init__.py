bl_info = {
    "name": "New Mitsuba2-Blender",
    "author": "Baptiste Nicolet",
    "version": (0, 1),
    "blender": (2, 80, 0),
    "category": "Exporter",
    "location": "File > Export > Mitsuba 2",
    "description": "Mitsuba2 export for Blender",
    "warning": "alpha0",
    "support": "TESTING"
}

import sys
import bpy
from .export import MitsubaFileExport, MitsubaPrefs
from .imp import MitsubaFileImport

def menu_func(self, context):
    self.layout.operator(MitsubaFileExport.bl_idname, text="Mitsuba 2 (.xml)")

def menu_func_import(self, context):
    self.layout.operator(MitsubaFileImport.bl_idname, text="Mitsuba 2 (.xml)")

def register():
    bpy.utils.register_class(MitsubaPrefs)
    
    bpy.utils.register_class(MitsubaFileExport)
    bpy.types.TOPBAR_MT_file_export.append(menu_func)

    bpy.utils.register_class(MitsubaFileImport)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)

def unregister():
    bpy.utils.unregister_class(MitsubaFileExport)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func)

    bpy.utils.unregister_class(MitsubaFileImport)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)

    bpy.utils.unregister_class(MitsubaPrefs)

if __name__ == '__main__':
    register()