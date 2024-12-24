from flask import Flask, render_template, request, jsonify
import spacy
from fuzzywuzzy import fuzz
import threading
from collections import defaultdict

# Инициализация spaCy для лемматизации
nlp = spacy.load("ru_core_news_sm", disable=["ner", "parser"])

# Стемминг и лемматизация текста
def preprocess_text(text):
    doc = nlp(text.lower())  # Приведение к нижнему регистру и лемматизация
    return [token.lemma_ for token in doc], doc  # Возвращаем также объект Doc для получения позиций в исходном тексте

# Поиск терминов с использованием нечёткого поиска
def find_terms(text, terms, threshold=90, progress_callback=None):
    text_tokens, doc = preprocess_text(text)
    matches = []
    total_terms = len(terms)
    processed_terms = 0

    for term in terms:
        term_tokens = preprocess_text(term.lower())[0]  # Лемматизация термина
        term_text = ' '.join(term_tokens)

        for i in range(len(text_tokens) - len(term_tokens) + 1):
            text_substring = ' '.join(text_tokens[i:i+len(term_tokens)])
            similarity = fuzz.ratio(text_substring, term_text)

            if similarity >= threshold:
                start_token = doc[i]
                end_token = doc[i + len(term_tokens) - 1]
                start = start_token.idx
                end = end_token.idx + len(end_token.text)

                matches.append({
                    "term": term,
                    "similarity": similarity,
                    "position": (start, end)
                })

        processed_terms += 1
        if progress_callback:
            progress_callback(processed_terms, total_terms)

    return matches

# Функция для чтения данных из файлов
def read_data(descriptions_files, terms_files):
    descriptions = []
    terms = []

    for desc_file in descriptions_files:
        with open(desc_file, 'r', encoding='utf-8') as file:
            descriptions.extend([desc.strip() for desc in file.readlines()])

    for terms_file in terms_files:
        with open(terms_file, 'r', encoding='utf-8') as file:
            terms.extend([term.strip().split(';') for term in file.readlines()])

    return descriptions, terms

# Основное приложение Flask
app = Flask(__name__)

# Глобальные переменные для хранения прогресса
progress_search = {"current": 0, "total": 0}
progress_process = {"current": 0, "total": 0}

# Чтение данных из файлов
descriptions_files = ['descriptions_org.txt', 'descriptions_mat_vid_aud.txt']
terms_files = ['terms_org.txt', 'terms_mat_vid_aud.txt']
descriptions, terms = read_data(descriptions_files, terms_files)
flat_terms = [term for sublist in terms for term in sublist if term]

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process():
    global progress_search
    text = request.form.get('text')

    # Сбрасываем прогресс
    progress_search["current"] = 0
    progress_search["total"] = len(flat_terms)

    def update_progress_search(processed, total):
        progress_search["current"] = processed
        progress_search["total"] = total

    # Запуск обработки в отдельном потоке
    threading.Thread(target=find_terms, args=(text, flat_terms, 80, update_progress_search)).start()

    return jsonify({"status": "started"})

@app.route('/progress', methods=['GET'])
def get_progress():
    global progress_search, progress_process
    return jsonify({
        "search": progress_search,
        "process": progress_process
    })

@app.route('/results', methods=['POST'])
def get_results():
    global progress_search, progress_process
    text = request.form.get('text')  # Получаем текст из тела запроса

    if progress_search["current"] < progress_search["total"]:
        return jsonify({"status": "processing"})

    # Если обработка завершена, возвращаем результаты
    matches = find_terms(text, flat_terms)

    # Сбрасываем прогресс обработки ответа
    progress_process["current"] = 0
    progress_process["total"] = len(matches)  # Общее количество совпадений

    # Сгруппируем вхождения по термину
    grouped_matches = defaultdict(list)
    for match in matches:
        grouped_matches[match['term']].append(match)

    # Объединяем группы с общими результатами
    combined_matches = []

    for term, term_matches in grouped_matches.items():
        # Найдем оригинальное описание для термина
        for desc, term_list in zip(descriptions, terms):
            if term in term_list:
                original_description = desc
                break
        else:
            original_description = "Описание не найдено"

        combined_matches.append({
            "term": term,
            "matches": term_matches,
            "description": original_description
        })

        # Обновляем прогресс обработки ответа
        progress_process["current"] += 1

    # Отсортируем совпадения по убыванию позиции
    combined_matches.sort(key=lambda x: x['matches'][0]['position'][0], reverse=True)

    # Выделяем совпадения в тексте
    result_html = ""
    used_positions = set()

    for group in combined_matches:
        term = group["term"]
        matches = group["matches"]
        description = group["description"]

        for match in matches:
            start, end = match["position"]

            # Получаем контекст вокруг совпадения
            context_start = max(0, start - 20)
            context_end = min(len(text), end + 20)
            context = text[context_start:start] + text[start:end] + text[end:context_end]

            result_html += f'<div class="match"><strong>Термин:</strong> {term}<br><strong>Контекст:</strong> {context}<br><strong>Описание:</strong> {description}</div><hr>'

    if len(combined_matches) == 0:
        result_html += f'<div class="match"><strong>Упоминаний не замечено!</strong></div><hr>'

    return jsonify(result_html)

if __name__ == '__main__':
    app.run(debug=True)