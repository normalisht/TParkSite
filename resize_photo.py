from PIL import Image
import os
import shutil


def get_size_format(b, factor=1024, suffix="B"):
    for unit in ["", "K", "M", "G", "T", "P", "E", "Z"]:
        if b < factor:
            return f"{b:.2f}{unit}{suffix}"
        b /= factor
    return f"{b:.2f}Y{suffix}"


def compress_img(image_name, new_size_ratio=1, quality=50, width=None, height=None, to_jpg=True):
    # load the image to memory
    img = Image.open(image_name)
    # print the original image shape
    # print("[*] Image shape:", img.size)
    # get the original image size in bytes
    image_size = os.path.getsize(image_name)
    # print the size before compression/resizing
    print("[*] Size before compression:", get_size_format(image_size))
    if new_size_ratio < 1.0:
        # if resizing ratio is below 1.0, then multiply width & height with this ratio to reduce image size
        img = img.resize((int(img.size[0] * new_size_ratio), int(img.size[1] * new_size_ratio)), Image.ANTIALIAS)
        # print new image shape
        # print("[+] New Image shape:", img.size)
    elif width and height:
        # if width and height are set, resize with them instead
        img.thumbnail((width, height), Image.ANTIALIAS)
        # print new image shape
        # print("[+] New Image shape:", img.size)
    # split the filename and extension
    filename, ext = os.path.splitext(image_name)
    # make new filename appending _compressed to the original file name
    if to_jpg:
        # change the extension to JPEG
        new_filename = f"{filename}.jpg"
    else:
        # retain the same extension of the original image
        new_filename = f"{filename}{ext}"
    try:
        # save the image with the corresponding quality and optimize set to True
        img.save(new_filename, quality=quality, optimize=True)
    except OSError:
        # convert the image to RGB mode first
        img = img.convert("RGB")
        # save the image with the corresponding quality and optimize set to True
        img.save(new_filename, quality=quality, optimize=True)
    # print("[+] New file saved:", new_filename)
    # get the new image size in bytes
    new_image_size = os.path.getsize(new_filename)
    # print the new size in a good format
    # print("[+] Size after compression:", get_size_format(new_image_size))
    # calculate the saving bytes
    saving_diff = new_image_size - image_size
    # print the saving percentage
    print(f"[+] Image size change: {saving_diff/image_size*100:.2f}% of the original image size.")


# directory = "app/static/images/category/1"
#
# for root, dirs, files in os.walk(directory):
#     for file in files:
#         if file.endswith('.jpg'):
#             compress_img(os.path.join(root, file), width=1920, height=1080)
#             # os.remove(os.path.join(root, file))
#
# directory = "app/static/images/service"
#
# for root, dirs, files in os.walk(directory):
#     for file in files:
#         if file.endswith('.jpg'):
#             file_name = file.split('.')[0]
#             new_dir = os.getcwd() + '/' + directory + '/' + file_name
#             os.makedirs(new_dir)
#             shutil.move(directory + '/' + file, new_dir)
weight = 75 # Вес
height = 175 # Рост
steps = 8462 # Количество пройденных за день шагов
hours = 2 # Время движения в часах
len_step_m = 0.65 # Длина одного шага в метрах
transfer_coeff = 1000 # Коэффициент перевода значения расстояния из метров в километры

dist = (steps * len_step_m) / transfer_coeff # Напишите формулу расчёта

mean_speed = dist / hours
minutes = hours * 60

spent_calories = (0.035*weight + (mean_speed**2 / height) * 0.029*weight) * minutes

congratulations = ()

if dist >= 7:
    congratulations = ('Отличный результат! Цель достигнута')
elif dist >= 3.9:
    congratulations = ('Неплохо! День был продуктивным')
elif dist >= 2:
    congratulations = ('Маловато, но завтра наверстаем')
else:
    congratulations = ('Лежать тоже полезно. Главное - участие, а не победа!')

output = (f'Сегодня вы прошли {dist:.2f} '
       f'км и затратили {spent_calories:.2f} '
       f'килокалорий. {congratulations}')  # Здесь подготовьте строку для вывода
# print(type(dist))
print (output)