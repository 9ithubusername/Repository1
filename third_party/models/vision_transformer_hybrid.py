
from copy import deepcopy
from functools import partial

import torch
import torch.nn as nn

from timm.data import IMAGENET_DEFAULT_MEAN, IMAGENET_DEFAULT_STD
from .layers import StdConv2dSame, StdConv2d, to_2tuple
from .resnet import resnet26d, resnet50d
from .resnetv2 import ResNetV2, create_resnetv2_stem
from .registry import register_model
from timm.models.vision_transformer import _create_vision_transformer


def _cfg(url='', **kwargs):
    return {
        'url': url,
        'num_classes': 1000, 'input_size': (3, 224, 224), 'pool_size': None,
        'crop_pct': .9, 'interpolation': 'bicubic',
        'mean': (0.5, 0.5, 0.5), 'std': (0.5, 0.5, 0.5),
        'first_conv': 'patch_embed.backbone.stem.conv', 'classifier': 'head',
        **kwargs
    }


default_cfgs = {
    'vit_base_r50_s16_224_in21k': _cfg(
        url='https://github.com/rwightman/pytorch-image-models/releases/download/v0.1-vitjx/jx_vit_base_resnet50_224_in21k-6f7c7740.pth',
        num_classes=21843, crop_pct=0.9),


    'vit_base_r50_s16_384': _cfg(
        url='https://github.com/rwightman/pytorch-image-models/releases/download/v0.1-vitjx/jx_vit_base_resnet50_384-9fd3c705.pth',
        input_size=(3, 384, 384), crop_pct=1.0),


    'vit_tiny_r_s16_p8_224': _cfg(),
    'vit_small_r_s16_p8_224': _cfg(),
    'vit_small_r20_s16_p2_224': _cfg(),
    'vit_small_r20_s16_224': _cfg(),
    'vit_small_r26_s32_224': _cfg(),
    'vit_base_r20_s16_224': _cfg(),
    'vit_base_r26_s32_224': _cfg(),
    'vit_base_r50_s16_224': _cfg(),
    'vit_large_r50_s32_224': _cfg(),

    'vit_small_resnet26d_224': _cfg(mean=IMAGENET_DEFAULT_MEAN, std=IMAGENET_DEFAULT_STD),
    'vit_small_resnet50d_s16_224': _cfg(mean=IMAGENET_DEFAULT_MEAN, std=IMAGENET_DEFAULT_STD),
    'vit_base_resnet26d_224': _cfg(mean=IMAGENET_DEFAULT_MEAN, std=IMAGENET_DEFAULT_STD),
    'vit_base_resnet50d_224': _cfg(mean=IMAGENET_DEFAULT_MEAN, std=IMAGENET_DEFAULT_STD),
}


class HybridEmbed(nn.Module):
    """ CNN Feature Map Embedding
    Extract feature map from CNN, flatten, project to embedding dim.
    """
    def __init__(self, backbone, img_size=224, patch_size=1, feature_size=None, in_chans=3, embed_dim=768):
        super().__init__()
        assert isinstance(backbone, nn.Module)
        img_size = to_2tuple(img_size)
        patch_size = to_2tuple(patch_size)
        self.img_size = img_size
        self.patch_size = patch_size
        self.backbone = backbone
        if feature_size is None:
            with torch.no_grad():
                training = backbone.training
                if training:
                    backbone.eval()
                o = self.backbone(torch.zeros(1, in_chans, img_size[0], img_size[1]))
                if isinstance(o, (list, tuple)):
                    o = o[-1]  
                feature_size = o.shape[-2:]
                feature_dim = o.shape[1]
                backbone.train(training)
        else:
            feature_size = to_2tuple(feature_size)
            if hasattr(self.backbone, 'feature_info'):
                feature_dim = self.backbone.feature_info.channels()[-1]
            else:
                feature_dim = self.backbone.num_features
        assert feature_size[0] % patch_size[0] == 0 and feature_size[1] % patch_size[1] == 0
        self.num_patches = feature_size[0] // patch_size[0] * feature_size[1] // patch_size[1]
        self.proj = nn.Conv2d(feature_dim, embed_dim, kernel_size=patch_size, stride=patch_size)

    def forward(self, x):
        x = self.backbone(x)
        if isinstance(x, (list, tuple)):
            x = x[-1]  
        x = self.proj(x).flatten(2).transpose(1, 2)
        return x


def _create_vision_transformer_hybrid(variant, backbone, pretrained=False, **kwargs):
    default_cfg = deepcopy(default_cfgs[variant])
    embed_layer = partial(HybridEmbed, backbone=backbone)
    kwargs.setdefault('patch_size', 1)  
    return _create_vision_transformer(
        variant, pretrained=pretrained, default_cfg=default_cfg, embed_layer=embed_layer, **kwargs)


def _resnetv2(layers=(3, 4, 9), **kwargs):
    """ ResNet-V2 backbone helper"""
    padding_same = kwargs.get('padding_same', True)
    if padding_same:
        stem_type = 'same'
        conv_layer = StdConv2dSame
    else:
        stem_type = ''
        conv_layer = StdConv2d
    if len(layers):
        backbone = ResNetV2(
            layers=layers, num_classes=0, global_pool='', in_chans=kwargs.get('in_chans', 3),
            preact=False, stem_type=stem_type, conv_layer=conv_layer)
    else:
        backbone = create_resnetv2_stem(
            kwargs.get('in_chans', 3), stem_type=stem_type, preact=False, conv_layer=conv_layer)
    return backbone


@register_model
def vit_base_r50_s16_224_in21k(pretrained=False, **kwargs):
    backbone = _resnetv2(layers=(3, 4, 9), **kwargs)
    model_kwargs = dict(embed_dim=768, depth=12, num_heads=12, representation_size=768, **kwargs)
    model = _create_vision_transformer_hybrid(
        'vit_base_r50_s16_224_in21k', backbone=backbone, pretrained=pretrained, **model_kwargs)
    return model


@register_model
def vit_base_resnet50_224_in21k(pretrained=False, **kwargs):
    return vit_base_r50_s16_224_in21k(pretrained=pretrained, **kwargs)


@register_model
def vit_base_r50_s16_384(pretrained=False, **kwargs):
    backbone = _resnetv2((3, 4, 9), **kwargs)
    model_kwargs = dict(embed_dim=768, depth=12, num_heads=12, **kwargs)
    model = _create_vision_transformer_hybrid(
        'vit_base_r50_s16_384', backbone=backbone, pretrained=pretrained, **model_kwargs)
    return model


@register_model
def vit_base_resnet50_384(pretrained=False, **kwargs):
    return vit_base_r50_s16_384(pretrained=pretrained, **kwargs)


@register_model
def vit_tiny_r_s16_p8_224(pretrained=False, **kwargs):
    backbone = _resnetv2(layers=(), **kwargs)
    model_kwargs = dict(patch_size=8, embed_dim=192, depth=12, num_heads=3, **kwargs)
    model = _create_vision_transformer_hybrid(
        'vit_tiny_r_s16_p8_224', backbone=backbone, pretrained=pretrained, **model_kwargs)
    return model


@register_model
def vit_small_r_s16_p8_224(pretrained=False, **kwargs):
    backbone = _resnetv2(layers=(), **kwargs)
    model_kwargs = dict(patch_size=8, embed_dim=384, depth=12, num_heads=6, **kwargs)
    model = _create_vision_transformer_hybrid(
        'vit_small_r_s16_p8_224', backbone=backbone, pretrained=pretrained, **model_kwargs)

    return model


@register_model
def vit_small_r20_s16_p2_224(pretrained=False, **kwargs):
    """ R52+ViT-S/S16 w/ 2x2 patch hybrid @ 224 x 224.
    """
    backbone = _resnetv2((2, 4), **kwargs)
    model_kwargs = dict(patch_size=2, embed_dim=384, depth=12, num_heads=6, **kwargs)
    model = _create_vision_transformer_hybrid(
        'vit_small_r20_s16_p2_224', backbone=backbone, pretrained=pretrained, **model_kwargs)
    return model


@register_model
def vit_small_r20_s16_224(pretrained=False, **kwargs):
    """ R20+ViT-S/S16 hybrid.
    """
    backbone = _resnetv2((2, 2, 2), **kwargs)
    model_kwargs = dict(embed_dim=384, depth=12, num_heads=6, **kwargs)
    model = _create_vision_transformer_hybrid(
        'vit_small_r20_s16_224', backbone=backbone, pretrained=pretrained, **model_kwargs)
    return model


@register_model
def vit_small_r26_s32_224(pretrained=False, **kwargs):
    """ R26+ViT-S/S32 hybrid.
    """
    backbone = _resnetv2((2, 2, 2, 2), **kwargs)
    model_kwargs = dict(embed_dim=384, depth=12, num_heads=6, **kwargs)
    model = _create_vision_transformer_hybrid(
        'vit_small_r26_s32_224', backbone=backbone, pretrained=pretrained, **model_kwargs)
    return model


@register_model
def vit_base_r20_s16_224(pretrained=False, **kwargs):
    """ R20+ViT-B/S16 hybrid.
    """
    backbone = _resnetv2((2, 2, 2), **kwargs)
    model_kwargs = dict(embed_dim=768, depth=12, num_heads=12, **kwargs)
    model = _create_vision_transformer_hybrid(
        'vit_base_r20_s16_224', backbone=backbone, pretrained=pretrained, **model_kwargs)
    return model


@register_model
def vit_base_r26_s32_224(pretrained=False, **kwargs):
    """ R26+ViT-B/S32 hybrid.
    """
    backbone = _resnetv2((2, 2, 2, 2), **kwargs)
    model_kwargs = dict(embed_dim=768, depth=12, num_heads=12, **kwargs)
    model = _create_vision_transformer_hybrid(
        'vit_base_r26_s32_224', backbone=backbone, pretrained=pretrained, **model_kwargs)
    return model


@register_model
def vit_base_r50_s16_224(pretrained=False, **kwargs):
    backbone = _resnetv2((3, 4, 9), **kwargs)
    model_kwargs = dict(embed_dim=768, depth=12, num_heads=12, **kwargs)
    model = _create_vision_transformer_hybrid(
        'vit_base_r50_s16_224', backbone=backbone, pretrained=pretrained, **model_kwargs)
    return model


@register_model
def vit_large_r50_s32_224(pretrained=False, **kwargs):
    """ R50+ViT-L/S32 hybrid.
    """
    backbone = _resnetv2((3, 4, 6, 3), **kwargs)
    model_kwargs = dict(embed_dim=768, depth=12, num_heads=12, **kwargs)
    model = _create_vision_transformer_hybrid(
        'vit_large_r50_s32_224', backbone=backbone, pretrained=pretrained, **model_kwargs)
    return model


@register_model
def vit_small_resnet26d_224(pretrained=False, **kwargs):
    backbone = resnet26d(pretrained=pretrained, in_chans=kwargs.get('in_chans', 3), features_only=True, out_indices=[4])
    model_kwargs = dict(embed_dim=768, depth=8, num_heads=8, mlp_ratio=3, **kwargs)
    model = _create_vision_transformer_hybrid(
        'vit_small_resnet26d_224', backbone=backbone, pretrained=pretrained, **model_kwargs)
    return model


@register_model
def vit_small_resnet50d_s16_224(pretrained=False, **kwargs):
    backbone = resnet50d(pretrained=pretrained, in_chans=kwargs.get('in_chans', 3), features_only=True, out_indices=[3])
    model_kwargs = dict(embed_dim=768, depth=8, num_heads=8, mlp_ratio=3, **kwargs)
    model = _create_vision_transformer_hybrid(
        'vit_small_resnet50d_s16_224', backbone=backbone, pretrained=pretrained, **model_kwargs)
    return model


@register_model
def vit_base_resnet26d_224(pretrained=False, **kwargs):
    backbone = resnet26d(pretrained=pretrained, in_chans=kwargs.get('in_chans', 3), features_only=True, out_indices=[4])
    model_kwargs = dict(embed_dim=768, depth=12, num_heads=12, **kwargs)
    model = _create_vision_transformer_hybrid(
        'vit_base_resnet26d_224', backbone=backbone, pretrained=pretrained, **model_kwargs)
    return model


@register_model
def vit_base_resnet50d_224(pretrained=False, **kwargs):
    backbone = resnet50d(pretrained=pretrained, in_chans=kwargs.get('in_chans', 3), features_only=True, out_indices=[4])
    model_kwargs = dict(embed_dim=768, depth=12, num_heads=12, **kwargs)
    model = _create_vision_transformer_hybrid(
        'vit_base_resnet50d_224', backbone=backbone, pretrained=pretrained, **model_kwargs)
    return model