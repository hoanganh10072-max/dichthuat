"""Real image decoding tests; none of these tests call a model."""
import io
import pytest
from PIL import Image
from app.image_translation import prepare_image


def encoded(image, fmt, **kwargs):
    stream=io.BytesIO(); image.save(stream, format=fmt, **kwargs)
    return stream.getvalue()


@pytest.mark.parametrize('fmt,name', [('PNG','source.PNG'),('JPEG','photo.jpeg'),('WEBP','scan.webp')])
def test_supported_real_formats(fmt,name):
    size,data,mime,notes=prepare_image(encoded(Image.new('RGB',(120,90),'white'),fmt),name)
    assert size==(120,90) and mime=='image/png' and notes==[]
    assert Image.open(io.BytesIO(data)).getpixel((0,0))==(255,255,255)


@pytest.mark.parametrize('mode', ['RGBA','LA','P'])
def test_transparent_background_is_white_and_ink_is_preserved(mode):
    original=Image.new('RGBA',(20,20),(0,0,0,0))
    original.putpixel((10,10),(0,0,0,255))
    if mode=='LA': original=original.convert('LA')
    if mode=='P': original=original.convert('P',palette=Image.Palette.ADAPTIVE)
    size,data,_,_=prepare_image(encoded(original,'PNG'),'transparent.png')
    output=Image.open(io.BytesIO(data))
    assert output.getpixel((0,0))==(255,255,255)
    assert output.getpixel((10,10))==(0,0,0)


def test_phone_exif_rotation_is_applied_before_coordinates():
    image=Image.new('RGB',(120,80),'white')
    exif=Image.Exif();exif[274]=6
    size,data,_,_=prepare_image(encoded(image,'JPEG',exif=exif),'phone.jpg')
    assert size==(80,120) and Image.open(io.BytesIO(data)).size==size


def test_cmyk_jpeg_is_readable():
    _,data,_,_=prepare_image(encoded(Image.new('CMYK',(40,30),'white'),'JPEG'),'cmyk.jpg')
    assert Image.open(io.BytesIO(data)).mode=='RGB'


@pytest.mark.parametrize('dimensions', [(5000,4000),(6000,6000)])
def test_large_phone_photo_is_scaled_instead_of_rejected(dimensions):
    size,_,_,notes=prepare_image(encoded(Image.new('RGB',dimensions,'white'),'PNG'),'large.png')
    assert size[0]*size[1]<=16_000_000 and abs(size[0]/size[1]-dimensions[0]/dimensions[1])<.002
    assert notes and '16 megapixel' in notes[0]


@pytest.mark.parametrize('data,name',[(b'', 'empty.png'),(b'not an image','corrupt.jpg'),
    (encoded(Image.new('RGB',(20,20)),'GIF'),'renamed.png'),
    (encoded(Image.new('RGB',(20,20)),'PNG'),'unsupported.heic')])
def test_invalid_and_disguised_files_are_rejected(data,name):
    with pytest.raises(ValueError):prepare_image(data,name)


def test_animated_webp_explains_first_frame_only():
    data=encoded(Image.new('RGB',(20,20),'white'),'WEBP',save_all=True,
        append_images=[Image.new('RGB',(20,20),'black')],duration=100,loop=0)
    size,_,_,notes=prepare_image(data,'animation.webp')
    assert size==(20,20) and 'khung hình đầu tiên' in notes[0]
