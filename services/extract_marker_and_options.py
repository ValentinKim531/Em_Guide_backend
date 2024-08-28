from constants.assistants_answers_var import (
    RegistrationQuestions,
    DailySurveyQuestions,
)
from utils.config import ASSISTANT2_ID, ASSISTANT_ID


def extract_marker_and_options(question_text, assistant_id):
    marker_start = question_text.find("[QUESTION_")
    if marker_start != -1:
        marker_end = question_text.find("]", marker_start)
        if marker_end != -1:
            question_marker = question_text[
                marker_start + 1 : marker_end
            ].strip()
            print(f"Extracted marker: {question_marker}")  # Отладочный вывод

            question_text = question_text[:marker_start].strip()

            if assistant_id == ASSISTANT2_ID:
                print(
                    f"Looking in RegistrationQuestions for {question_marker}"
                )
                options_data = RegistrationQuestions.__members__.get(
                    question_marker
                )
                if options_data:
                    options_data = options_data.value
            elif assistant_id == ASSISTANT_ID:
                print(f"Looking in DailySurveyQuestions for {question_marker}")
                options_data = DailySurveyQuestions.__members__.get(
                    question_marker
                )
                if options_data:
                    options_data = options_data.value
            else:
                options_data = None

            return question_text, options_data

    return question_text, None
