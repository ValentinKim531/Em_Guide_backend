from enum import Enum


class RegistrationQuestions(Enum):
    QUESTION_1 = {
        "options": [],
        "is_custom_option_allowed": True,
    }
    QUESTION_2 = {
        "options": ["Да", "Нет"],
        "is_custom_option_allowed": False,
    }
    QUESTION_3 = {
        "options": [],
        "is_custom_option_allowed": True,
    }
    QUESTION_4 = {
        "options": ["Да", "Нет"],
        "is_custom_option_allowed": True,  # Если "Да", то нужен свой вариант
    }
    QUESTION_5 = {
        "options": ["Да", "Нет"],
        "is_custom_option_allowed": True,  # Если "Да", то нужен свой вариант
    }


class DailySurveyQuestions(Enum):
    QUESTION_1 = {
        "options": ["Да", "Нет"],
        "is_custom_option_allowed": True,  # Если "Да", то нужен свой вариант
    }
    QUESTION_2 = {
        "options": ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"],
        "is_custom_option_allowed": False,
    }
    QUESTION_3 = {
        "options": [
            "висок",
            "теменная область",
            "бровь",
            "глаз",
            "верхняя челюсть",
            "нижняя челюсть",
            "лоб",
            "затылок",
        ],
        "is_custom_option_allowed": True,  # Можно указать свой вариант ответа
    }
    QUESTION_4 = {
        "options": [
            "с одной стороны справа",
            "с одной стороны слева",
            "с двух сторон",
        ],
        "is_custom_option_allowed": True,  # Можно указать свой вариант ответа
    }
    QUESTION_5 = {
        "options": [
            "давящая",
            "пульсирующая",
            "сжимающая",
            "ноющая",
            "ощущение прострела",
            "режущая",
            "тупая",
            "пронизывающая",
            "острая",
            "жгучая",
        ],
        "is_custom_option_allowed": True,  # Можно указать свой вариант ответа
    }
