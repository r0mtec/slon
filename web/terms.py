import re

# Открываем исходный файл для чтения
with open('test_web/descriptions_mat_vid_aud.txt', 'r', encoding='utf-8') as input_file:
    lines = input_file.readlines()

# Открываем файл для записи результата
with open('test_web/terms_mat_vid_aud.csv', 'w', encoding='utf-8') as output_file:
    for i, line in enumerate(lines, start=1):
        # Ищем все фрагменты между ""...""
        matches = re.findall(r'""(.*?)""', line)
        if matches:
            # Объединяем все найденные фрагменты через ;
            result = ";".join(matches)
            # Записываем в файл с сохранением нумерации строк
            output_file.write(f"{result}\n")
        else:
            output_file.write("\n")