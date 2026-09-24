"""Deterministic procedural woven carpet texture, physical tile width 0.50m."""
import numpy as np
from scipy.ndimage import gaussian_filter
from PIL import Image
from pathlib import Path
root=Path(__file__).resolve().parents[1];rng=np.random.default_rng(2209);n=1024;y,x=np.mgrid[:n,:n]
warp=gaussian_filter(rng.normal(size=(n,n)),[14,45])*18
fiber=np.sin(y*2*np.pi/7+warp)*.012+np.sin(y*.39+x*.004)*.009
slub=gaussian_filter(rng.normal(size=(n,n)),[.55,5])*.20
macro=gaussian_filter(rng.normal(size=(n,n)),[6,18])*.50
v=np.clip(.31+fiber+slub+macro+rng.normal(0,.018,(n,n)),.13,.52)
rgb=np.stack([v*.995,v*1.015,v*.97],axis=-1)
Image.fromarray(np.uint8(rgb*255)).save(root/'evidence/carpet_calibrated_0.png')
Image.fromarray(np.uint8(np.rot90(rgb)*255)).save(root/'evidence/carpet_calibrated_1.png')
