"""
Compatibility utilities for LanguageBind with newer transformers versions.
Provides missing functions that were removed in newer transformers versions.
"""
import torch
from typing import Optional


def _expand_mask(mask: torch.Tensor, dtype: torch.dtype, tgt_len: Optional[int] = None):
    """
    Expands attention_mask from `[bsz, seq_len]` to `[bsz, 1, tgt_seq_len, src_seq_len]`.
    
    This function was removed from transformers in newer versions but is needed by LanguageBind.
    Copied from transformers v4.6.0 for compatibility.
    """
    bsz, src_len = mask.size()
    tgt_len = tgt_len if tgt_len is not None else src_len

    expanded_mask = mask[:, None, None, :].expand(bsz, 1, tgt_len, src_len).to(dtype)

    inverted_mask = 1.0 - expanded_mask

    return inverted_mask.masked_fill(inverted_mask.bool(), torch.finfo(dtype).min)


def clip_loss(similarity: torch.Tensor) -> torch.Tensor:
    """
    Contrastive loss function for CLIP.
    Adapted from https://sachinruk.github.io/blog/pytorch/pytorch%20lightning/loss%20function/gpu/2021/03/07/CLIP.html
    """
    import torch.nn.functional as F
    
    def contrastive_loss(logits: torch.Tensor, dim: int) -> torch.Tensor:
        neg_ce = torch.diag(F.log_softmax(logits, dim=dim))
        return -neg_ce.mean()
    
    caption_loss = contrastive_loss(similarity, dim=0)
    image_loss = contrastive_loss(similarity, dim=1)
    return (caption_loss + image_loss) / 2.0


class CLIPOutput:
    """
    Compatibility class for CLIP output.

    Args:
        loss (`torch.FloatTensor` of shape `(1,)`, *optional*, returned when `return_loss` is `True`):
            Contrastive loss for image-text similarity.
        logits_per_image (`torch.FloatTensor` of shape `(image_batch_size, text_batch_size)`):
            The scaled dot product scores between `image_embeds` and `text_embeds`.
        logits_per_text (`torch.FloatTensor` of shape `(text_batch_size, image_batch_size)`):
            The scaled dot product scores between `text_embeds` and `image_embeds`.
        text_embeds (`torch.FloatTensor` of shape `(batch_size, output_dim)`):
            The text embeddings obtained by applying the projection layer.
        image_embeds (`torch.FloatTensor` of shape `(batch_size, output_dim)`):
            The image embeddings obtained by applying the projection layer.
        text_model_output (`BaseModelOutputWithPooling`):
            The output of the text model.
        vision_model_output (`BaseModelOutputWithPooling`):
            The output of the vision model.
    """
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

