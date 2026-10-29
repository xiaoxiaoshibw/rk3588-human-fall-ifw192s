"""Warm light presentation of the existing offline point-cloud replay."""
import numpy as np
from PIL import Image, ImageDraw, ImageOps
import render_full_video as core

PAPER=(247,245,239)
PANEL=(253,252,248)
INK=(52,48,43)
MUTED=(124,115,103)
ACCENT=(194,101,73)


def light_cloud(image):
    """Recolour only the existing display pixels, preserving their coordinates."""
    source=np.asarray(image)
    out=np.empty_like(source)
    out[:]=PANEL
    palette={
        (87,122,137):(152,145,133), (73,100,118):(155,148,136),
        (70,232,154):ACCENT, (94,255,170):(166,76,52),
        (37,63,73):(222,215,204),
    }
    for old,new in palette.items():
        out[np.all(source==old,axis=2)]=new
    return Image.fromarray(out)


def render(row,xyz,title,seq,center,camera_dir,fonts,level):
    small,label,heading=fonts
    im=Image.new('RGB',(core.WIDTH,core.HEIGHT),PAPER)
    d=ImageDraw.Draw(im)
    d.rounded_rectangle((24,24,61,61),radius=10,fill=ACCENT)
    d.line((42,33,42,52),fill=(255,253,248),width=2)
    d.line((33,42,51,42),fill=(255,253,248),width=2)
    d.text((74,29),'LIDAR  /  人体检测',font=small,fill=MUTED)
    d.text((25,67),title,font=heading,fill=INK)
    d.text((1450,81),'%02d  /  04'%seq,font=label,fill=MUTED)
    boxes=[(20,170),(415,170),(810,170),(1205,170)]
    for (x,y),caption in zip(boxes,['完整点云 · 3D','正面点云','侧面点云','相机画面']):
        d.rounded_rectangle((x,y-42,x+380,y+470),radius=12,fill=PANEL,outline=(224,218,208),width=1)
        d.text((x+14,y-34),caption,font=small,fill=INK)
    scene,shown=core.full_panel(xyz,row,center)
    im.paste(light_cloud(scene),boxes[0])
    im.paste(light_cloud(core.base.cloud_panel(row,'front',center,size=(380,470))),boxes[1])
    im.paste(light_cloud(core.base.cloud_panel(row,'side',center,size=(380,470))),boxes[2])
    pos=core.target_position(row)
    if row.get('tid') and row.get('n'):
        for panel in range(3):
            point=core.label_position(row,center,panel)
            if point is not None:
                x,y=boxes[panel][0]+point[0],boxes[panel][1]+point[1]
                rect=d.textbbox((x,y),'人体',font=small)
                d.rounded_rectangle((rect[0]-5,rect[1]-3,rect[2]+5,rect[3]+3),radius=5,fill=(249,232,221))
                d.text((x,y),'人体',font=small,fill=(143,63,42))
    if row['cam']:
        camera=Image.open(camera_dir/('c%03d.jpg'%row['cam'][0])).convert('RGB')
        camera=ImageOps.contain(camera,(380,470),method=Image.Resampling.LANCZOS)
        im.paste(camera,(1205+(380-camera.width)//2,170+(470-camera.height)//2))
    else:
        d.text((1268,350),'相机帧不可用',font=small,fill=MUTED)
    alert=level>0
    state=core.posture(row,level)
    d.rounded_rectangle((20,669,1585,744),radius=14,
                        fill=(250,227,217) if alert else (237,234,225),
                        outline=(222,163,139) if alert else (225,219,208))
    d.ellipse((44,699,54,709),fill=ACCENT if alert else (154,164,141))
    d.text((67,688),'人体状态  '+state,font=label,fill=(153,64,45) if alert else INK)
    d.text((1210,688),'倒地报警' if level==2 else '疑似倒地报警' if alert else '未触发报警',
           font=label,fill=(153,64,45) if alert else MUTED)
    coords=('人体位置：未知' if row.get('tid') and row.get('n') else '人体位置：未锁定') if pos is None else '人体位置  /  X %.2f    Y %.2f    Z %.2f m'%tuple(pos)
    d.text((25,775),coords,font=small,fill=INK)
    d.text((1450,790),'%05.1f s'%row['t'],font=small,fill=MUTED)
    return im,shown


if __name__=='__main__':
    core.render=render
    core.main()
