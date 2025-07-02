import os
for service_id in os.listdir('app/static/images/service'):
    counter = 3
    folder_path = 'app/static/images/service/{}'.format(service_id)
    if not os.path.isdir(folder_path):
        continue
    for filename in os.listdir('app/static/images/service/{}'.format(service_id)):
        old_file_path = os.path.join(folder_path, filename)
        if not os.path.isfile(old_file_path):
            continue
        file_extension = os.path.splitext(filename)[1]
        new_filename = f"file_{counter}{file_extension}"
        new_file_path = os.path.join(folder_path, new_filename)
        os.rename(old_file_path, new_file_path)
        counter += 1
    counter = 3
    for filename in os.listdir('app/static/images/service/{}'.format(service_id)):
        old_file_path = os.path.join(folder_path, filename)
        if not os.path.isfile(old_file_path):
            continue
        file_extension = os.path.splitext(filename)[1]
        new_filename = f"{counter}{file_extension}"
        new_file_path = os.path.join(folder_path, new_filename)
        os.rename(old_file_path, new_file_path)
        counter += 1
