"""Independent Krea2 node pack. Does not modify H3, Qwen, or Identity Edit nodes."""
from .krea2_character_sheet.node import Krea2CharacterSheetDesigner, Krea2LayoutReferenceSheetDesigner
from .krea2_character_sheet.preview import register_routes

NODE_CLASS_MAPPINGS = {
    'Krea2CharacterSheetDesigner': Krea2CharacterSheetDesigner,
    'Krea2LayoutReferenceSheetDesigner': Krea2LayoutReferenceSheetDesigner,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    'Krea2CharacterSheetDesigner': 'Krea2 Character Sheet Designer',
    'Krea2LayoutReferenceSheetDesigner': 'Krea2 Layout Reference Sheet Designer (Experimental)',
}
WEB_DIRECTORY = './web'
register_routes()
__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS', 'WEB_DIRECTORY']
