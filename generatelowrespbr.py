import os
from os import remove

import PIL
from PIL import Image


def image_file_filter(file_list):
    """
    Generator returning, from file_list, only the filename of images with extensions png and jpg
    """
    for f_name in (f for f in file_list if os.path.splitext(f)[1] in ('.png', '.jpg')):
        yield f_name


# This script generates low resolution of all PBR textures
# High resolution textures are only used in Best mode
root_dir = os.path.expandvars('$HBP/Models')

# First remove all low res versions
print("Clean low resolution textures")

for path, _, files in os.walk(root_dir):

    for image_file in image_file_filter(files):

        if image_file.startswith(("LOWPBRFULL_", "LOWPBR_", "_Height", "LOWSKY_")):
            try:
                print("\tRemoving %s" % image_file)
                remove(os.path.join(path, image_file))
            except OSError as e:
                print(e)

# Generate low resolution versions of PBR
print("Generate low resolution textures")

for path, _, files in os.walk(root_dir):

    for image_file in image_file_filter(files):
        if image_file.startswith(('PBRFULL_', 'PBR_')):
            print("\t%s" % image_file)

            img = Image.open(os.path.join(path, image_file))

            w, h = img.size

            if (w, h) > (1, 1):
                new_w, new_h = int(w/2), int(h/2)

                if 'Mixed_AO' in image_file:
                    max_size = 256
                elif image_file.endswith(('_Metallic', '_Roughness')):
                    max_size = 512
                else:
                    max_size = new_w

                new_w, new_h = min(new_w, max_size), min(new_h, max_size)

                resample_filter = PIL.Image.NEAREST if '_Normal' not in image_file else PIL.Image.LANCZOS
                img = img.resize((new_w, new_h), resample_filter)

            image_path = os.path.join(path, 'LOW' + image_file)

            print("\tSaving: %s" % image_file)

            img.save(image_path)


# Generate low resolution versions of sky env. map

print("Generate low resolution of sky textures")

root_dir = os.path.expandvars('$HBP/Models/sky')

sky_file_prefix = "LOWSKY_"

for path, _, files in os.walk(root_dir):

    for image_file in image_file_filter(files):

        if not image_file.startswith(sky_file_prefix):
            print("\t%s" % image_file)
            img = Image.open(os.path.join(path, image_file))

            w, h = img.size

            img_resized = img.resize((int(w/2),  int(h/2)), resample=PIL.Image.LANCZOS)

            image_path = os.path.join(path, sky_file_prefix + image_file)

            print("\tSaving: %s" % image_file)

            img_resized.save(image_path, quality=95)
        else:
            print("Found 'LOWSKY_' Texture after cleanup! SKIP")
