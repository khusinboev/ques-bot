from datetime import datetime

from config import cursor


def get_last_5_results(user_id: int, subject: str):
    subject = subject.lower()
    if subject not in ["math", "literature", "history"]:
        raise ValueError("Noto‘g‘ri fan nomi!")

    query = f"""
        SELECT number, finished_at FROM results
        WHERE user_id = %s AND {subject} = TRUE
        ORDER BY finished_at DESC
        LIMIT 5
    """
    cursor.execute(query, (user_id,))
    return cursor.fetchall()


def format_results(user_id: int) -> str:
    fanlar = {
        "math": "📘 Matematika",
        "literature": "📗 Ona tili",
        "history": "📙 Tarix"
    }

    matn = "<b>📊 So‘nggi test natijalaringiz:</b>\n\n"

    for subject, title in fanlar.items():
        natijalar = get_last_5_results(user_id, subject)
        if not natijalar:
            continue

        matn += f"{title}:\n"
        for idx, (number, finished_at) in enumerate(natijalar, 1):
            score = round(number * 1.1, 1)
            time_str = finished_at.strftime("%Y-%m-%d %H:%M")
            matn += f"{idx}. {number} ta to‘g‘ri javob | {score} ball | {time_str}\n"
        matn += "\n"

    return matn if matn.strip() != "<b>📊 So‘nggi test natijalaringiz:</b>" else "Siz hali hech qanday test yechmagansiz."
