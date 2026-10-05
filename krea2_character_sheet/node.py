"""Two role-specific nodes share the exact same canonical Designer state."""
import importlib
import json
from .compiler import DEFAULT_STATE_JSON, StateValidationError, compile_state


# Krea starting point matches the successful five-view sheet dimensions.
# This is an ordinary v1 state; imported H3/Qwen states are never rewritten.
DEFAULT_NODE_STATE_JSON = json.dumps({
    'schema_version': 1,
    'views': ['face_front', 'face_left', 'body_front', 'body_left', 'body_back'],
    'size': {'mode': 'manual', 'body_height': 672, 'manual_width': 1696, 'manual_height': 768},
}, separators=(',', ':'))

def runtime_max_resolution() -> int:
    maximum = importlib.import_module('nodes').MAX_RESOLUTION
    if type(maximum) is not int or maximum < 32:
        raise RuntimeError('ComfyUI nodes.MAX_RESOLUTION must be an integer of at least 32.')
    return maximum


class Krea2CharacterSheetDesigner:
    CATEGORY = 'Krea2/CharacterSheet'
    DESCRIPTION = ('Character reference required. Connect prompt to Krea2EditGroundedEncode; '
                   'connect width/height to EmptySD3LatentImage and share that latent with '
                   'KSampler and Krea2EditModelPatch.target_latent. The UI mannequin is never a generation input.')
    RETURN_TYPES = ('STRING', 'INT', 'INT')
    RETURN_NAMES = ('prompt', 'width', 'height')
    FUNCTION = 'compile'
    LAYOUT_REFERENCE = False

    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'state_json': ('STRING', {
            'default': DEFAULT_NODE_STATE_JSON, 'multiline': True, 'dynamicPrompts': False,
        })}}

    @classmethod
    def VALIDATE_INPUTS(cls, state_json):
        try:
            compile_state(state_json, max_resolution=runtime_max_resolution(), layout_reference=cls.LAYOUT_REFERENCE)
        except StateValidationError as exc:
            return str(exc)
        return True

    def compile(self, state_json):
        result = compile_state(state_json, max_resolution=runtime_max_resolution(), layout_reference=self.LAYOUT_REFERENCE)
        return result['prompt'], result['width'], result['height']


class Krea2LayoutReferenceSheetDesigner(Krea2CharacterSheetDesigner):
    DESCRIPTION = ('Experimental two-reference variant. Image 1 = layout example; Image 2 = character identity. '
                   'Use the supplied two-reference workflow. Both images influence generation; '
                   'layout-only isolation and exact geometry are not guaranteed. No automatic atlas image input.')
    LAYOUT_REFERENCE = True
