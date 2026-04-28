import os
import re
import base64
from pathlib import Path

import streamlit as st
from openai import OpenAI

st.set_page_config(page_title="BIO AI", page_icon="🧠", layout="wide")

st.markdown("""
<style>

/* TŁO */
.stApp {
    background-color: #0e1117;
    color: #ffffff;
}

/* GŁÓWNY TEKST */
body, .stMarkdown, .stText, p, div {
    color: #ffffff !important;
}

/* CHAT */
[data-testid="stChatMessage"] {
    background-color: #1a1f2b;
    border-radius: 15px;
    padding: 10px;
    margin-bottom: 10px;
}

/* USER */
[data-testid="stChatMessage"][data-testid*="user"] {
    background-color: #0d3b66;
}

/* INPUT */
textarea, input {
    background-color: #1a1f2b !important;
    color: white !important;
}

/* SIDEBAR */
section[data-testid="stSidebar"] {
    background-color: #111827;
}

/* SELECTBOX */
div[data-baseweb="select"] {
    background-color: #1a1f2b !important;
    color: white !important;
}

/* BUTTON */
button {
    background-color: #2563eb !important;
    color: white !important;
    border-radius: 10px !important;
}

/* TITLE */
.main-title {
    color: #60a5fa;
}

/* SUBTITLE */
.subtitle {
    color: #94a3b8;
}

/* CARD */
.info-card {
    background: #1a1f2b;
    border: 1px solid #374151;
    color: white;
}

/* LEVEL BOX */
.level-box {
    background: #2563eb;
    color: white;
}

</style>
""", unsafe_allow_html=True)

# API KEY
# Lokalnie najlepiej:
# set OPENAI_API_KEY=twój_klucz
client = OpenAI(api_key="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")

PROMPTS_DIR = Path("prompts")
DATA_DIR = Path("data")
SLOWNIKI_DIR = DATA_DIR / "slowniki"

PLAN_FILE = DATA_DIR / "plan nauki.dat"
ZAKRES_FILE = DATA_DIR / "zakres podstawy programowej.dat"

SKIP_FILES = {
    "plan nauki.dat",
    "zakres podstawy programowej.dat",
}


def read_dat_file(file_path: Path) -> str:
    encoded = file_path.read_text(encoding="utf-8")
    return base64.b64decode(encoded.encode("ascii")).decode("utf-8")


def load_dat_files(folder: Path) -> str:
    if not folder.exists():
        return ""

    texts = []
    for file in sorted(folder.glob("*.dat")):
        texts.append(f"\n--- PLIK: {file.name} ---\n{read_dat_file(file)}")

    return "\n".join(texts)


def load_core_context() -> str:
    parts = []

    if PLAN_FILE.exists():
        parts.append(f"\n--- PLAN NAUKI ---\n{read_dat_file(PLAN_FILE)}")

    if ZAKRES_FILE.exists():
        parts.append(f"\n--- ZAKRES PODSTAWY PROGRAMOWEJ ---\n{read_dat_file(ZAKRES_FILE)}")

    return "\n".join(parts)


def clean_words(text: str):
    text = text.lower()
    text = re.sub(r"[^a-ząćęłńóśźż0-9+\- ]", " ", text)
    return text.split()


def get_file_topics(file_path: Path):
    try:
        lines = read_dat_file(file_path).splitlines()

        for line in lines:
            line = line.strip()
            if line.startswith("TEMAT:"):
                topics = line.replace("TEMAT:", "").strip()
                return [t.strip().lower() for t in topics.split(",")]

    except Exception:
        pass

    return []


def select_relevant_files(user_input: str, max_files: int = 2):
    user_words = clean_words(user_input)
    scored_files = []

    for file in DATA_DIR.glob("*.dat"):
        if file.name in SKIP_FILES:
            continue

        topics = get_file_topics(file)
        score = 0

        for word in user_words:
            for topic in topics:
                if word in topic:
                    score += 1

        if score > 0:
            scored_files.append((score, file))

    scored_files.sort(reverse=True, key=lambda x: x[0])
    return [f for _, f in scored_files[:max_files]]


def build_selected_content(user_input: str):
    selected_files = select_relevant_files(user_input)

    selected_content = ""

    for file in selected_files:
        selected_content += f"\n--- PLIK: {file.name} ---\n{read_dat_file(file)}"

    if not selected_content.strip():
        selected_content = "Brak jednoznacznie dopasowanego pliku tematycznego."

    return selected_content


def parse_glossary_file(file_path: Path):
    content = read_dat_file(file_path)
    entries = []
    current = {}

    for line in content.splitlines():
        line = line.strip()

        if not line:
            if current:
                entries.append(current)
                current = {}
            continue

        if line.startswith("HASŁO:"):
            current["haslo"] = line.replace("HASŁO:", "").strip()
        elif line.startswith("KRÓTKO:"):
            current["krotko"] = line.replace("KRÓTKO:", "").strip()
        elif line.startswith("MECHANIZM:"):
            current["mechanizm"] = line.replace("MECHANIZM:", "").strip()
        elif line.startswith("BŁĄD:"):
            current["blad"] = line.replace("BŁĄD:", "").strip()

    if current:
        entries.append(current)

    return entries


def update_level(answer: str, level: int):
    upper = answer.upper()

    if "LEVEL_CHANGE: UP" in upper:
        return min(level + 1, 5)
    elif "LEVEL_CHANGE: DOWN" in upper:
        return max(level - 1, 1)

    return level


levels_prompt = """
System poziomów trudności:

Poziom 1 — fundament
Poziom 2 — mechanizm
Poziom 3 — zależności
Poziom 4 — zastosowanie
Poziom 5 — integracja

Zasady:
- poprawna, mechanistyczna odpowiedź → zaproponuj poziom wyżej
- częściowa odpowiedź → zostań na poziomie
- błędna odpowiedź → poziom niżej i odbuduj mechanizm
- nie nagradzaj definicji

Zmieniaj poziom tylko wtedy, gdy użytkownik faktycznie odpowiada merytorycznie na pytanie albo rozwiązuje zadanie.
Jeśli użytkownik tylko prosi o wyjaśnienie, wpisz:
LEVEL_CHANGE: SAME

Na końcu odpowiedzi wpisz dokładnie jedną linię:
LEVEL_CHANGE: UP
albo
LEVEL_CHANGE: SAME
albo
LEVEL_CHANGE: DOWN
"""


prompts = load_dat_files(PROMPTS_DIR)
core_context = load_core_context()

system_prompt = f"""
Jesteś AI-tutorem biologii rozszerzonej.

DOMYŚLNA DŁUGOŚĆ ODPOWIEDZI:
- Standardowa odpowiedź powinna mieć maksymalnie 450 słów.
- Jeśli użytkownik prosi o krótkie wyjaśnienie, odpowiedz krócej: 150–250 słów.
- Jeśli użytkownik prosi o dokładne omówienie, możesz przekroczyć limit 450 słów.
- W trybie lekcji limit 450 słów nie obowiązuje sztywno, ale nadal omawiaj tylko jeden etap naraz.
- Jeśli temat jest bardzo szeroki i pełna odpowiedź przekroczyłaby limit, nie omawiaj wszystkiego naraz.
  Zamiast tego:
  1. krótko rozpisz, z jakich części składa się temat,
  2. wskaż pierwszy logiczny krok,
  3. zaproponuj przejście po kolei.
- Nie rozbudowuj odpowiedzi akademicko, jeśli użytkownik nie poprosił o głębsze wyjaśnienie.
- Nie omawiaj wszystkich powiązań naraz. Wybierz 1–2 najważniejsze powiązania.

OGRANICZENIE DOMENY:
Jesteś tutorem biologii, nie ogólnym chatbotem.
Odpowiadasz tylko z biologii oraz chemii/fizyki potrzebnej do biologii.
Jeśli użytkownik pyta o temat spoza biologii, odpowiedz krótko:
„To wykracza poza zakres tego tutora. Ten program służy do nauki biologii i potrzebnych do niej elementów chemii oraz fizyki. Wróćmy do układu nerwowego.”
Nie tłumacz takiego tematu.

Poniższe pliki z folderu prompts/ są nadrzędnymi zasadami rozmowy.
Masz się ich trzymać przez całą rozmowę.

{prompts}

Zasady korzystania z danych:
- Nie traktuj całego folderu data/ jako wyznacznika zakresu materiału.
- Zakres obowiązującego materiału określa wyłącznie plik: "zakres podstawy programowej.dat".
- Pliki tematyczne z folderu data/ służą jako pomocnicze notatki do tłumaczenia konkretnych tematów.
- Pliki tematyczne nie określają granic materiału.
- Możesz korzystać z własnej wiedzy biologicznej, jeśli pomaga poprawnie wyjaśnić temat.
- Jeśli dane z plików są sprzeczne z poprawną biologią, nie powtarzaj błędu; zaznacz problem.
- Jeżeli pytanie dotyczy czegoś obecnego w danych, użyj tych danych jako punktu wyjścia.
"""


def build_developer_context(user_input: str, level: int):
    selected_content = build_selected_content(user_input)

    return f"""
PRIORYTET BEZPIECZNIKA TEMATYCZNEGO:
Jeśli użytkownik prosi o temat niezwiązany z biologią, nie odpowiadaj merytorycznie na ten temat, nawet jeśli użytkownik nalega.
Program jest ograniczony do biologii oraz biologicznie potrzebnej chemii i fizyki.

TRYB LEKCJI:
Jeśli użytkownik używa fraz typu: "zacznij od podstaw", "wytłumacz krok po kroku", "nie rozumiem", "ucz mnie", "następny krok", "kontynuuj", uruchom tryb lekcji.

1. PLAN NAUKI
Plan nauki określa zalecaną kolejność omawiania działu, ale używaj go tylko wtedy, gdy użytkownik chce nauki prowadzonej po kolei.

Nie używaj planu nauki do cofania użytkownika do wcześniejszych tematów, jeśli zadaje konkretne pytanie.
Jeśli użytkownik pyta o konkretny temat, odpowiedz na ten temat bez zaczynania od wcześniejszych etapów.

Przykład:
Jeśli użytkownik pyta o receptory, tłumacz receptory.
Nie zaczynaj od budowy neuronu tylko dlatego, że neuron jest wcześniej w planie.

2. ZAKRES PODSTAWY PROGRAMOWEJ
Zakres podstawy programowej określa domyślny poziom i granice materiału.
Domyślnie tłumacz na poziomie biologii rozszerzonej w liceum, bez zbędnego wchodzenia w szczegóły akademickie.

Jeśli temat wykracza poza podstawę programową:
- możesz wspomnieć go krótko, jeśli pomaga zrozumieć mechanizm,
- ale nie rozwijaj go nadmiernie bez prośby użytkownika.

Jeśli użytkownik wyraźnie prosi o głębsze wyjaśnienie, możesz wyjść poza podstawę, ale zaznacz:
"To jest już poza podstawą, ale pomaga zrozumieć mechanizm."

AKTUALNY POZIOM UCZNIA:
{level}

SYSTEM POZIOMÓW:
{levels_prompt}

STAŁY KONTEKST:
{core_context}

KONTEKST TEMATYCZNY — wybrane pliki pasujące do pytania:
{selected_content}
"""


if "messages" not in st.session_state:
    st.session_state.messages = []

if "pending_prompt" not in st.session_state:
    st.session_state.pending_prompt = None

if "level" not in st.session_state:
    st.session_state.level = 2


with st.sidebar:
    st.markdown("## 🧠 BIO AI")
    st.caption("Tutor biologii rozszerzonej")

    st.markdown(
        f"<div class='level-box'>Poziom ucznia: {st.session_state.level}/5</div>",
        unsafe_allow_html=True
    )

    st.divider()

    if st.button("🧹 Wyczyść rozmowę"):
        st.session_state.messages = []
        st.session_state.pending_prompt = None
        st.session_state.level = 2
        st.rerun()

    st.divider()

    st.header("📚 Słowniczek")

    glossary_files = sorted(SLOWNIKI_DIR.glob("*.dat")) if SLOWNIKI_DIR.exists() else []

    if not glossary_files:
        st.info("Brak słowniczków w folderze data/slowniki.")
    else:
        selected_glossary = st.selectbox(
            "Wybierz dział:",
            glossary_files,
            format_func=lambda x: x.stem.replace("_", " ")
        )

        entries = parse_glossary_file(selected_glossary)

        if entries:
            selected_entry = st.selectbox(
                "Wybierz pojęcie:",
                entries,
                format_func=lambda x: x.get("haslo", "Brak hasła")
            )

            st.markdown("### 🔎 Podgląd")
            st.markdown(f"**{selected_entry.get('haslo', '')}**")
            st.write(f"**Krótko:** {selected_entry.get('krotko', '')}")
            st.write(f"**Mechanizm:** {selected_entry.get('mechanizm', '')}")
            st.write(f"**Częsty błąd:** {selected_entry.get('blad', '')}")

            if st.button("✨ Wyjaśnij w czacie"):
                st.session_state.pending_prompt = f"""
Wyjaśnij pojęcie ze słowniczka:

HASŁO: {selected_entry.get('haslo', '')}
KRÓTKO: {selected_entry.get('krotko', '')}
MECHANIZM: {selected_entry.get('mechanizm', '')}
CZĘSTY BŁĄD: {selected_entry.get('blad', '')}

Wyjaśnij:
1. intuicyjnie,
2. mechanistycznie,
3. pokaż typowy błąd,
4. pokaż jedno ważne powiązanie z innym pojęciem.

Nie rób quizu na końcu.
"""
                st.rerun()


st.markdown("<div class='main-title'>🧠 BIO AI — układ nerwowy</div>", unsafe_allow_html=True)
st.markdown(
    "<div class='subtitle'>Zadaj pytanie, poproś o lekcję krok po kroku albo wybierz pojęcie ze słowniczka.</div>",
    unsafe_allow_html=True
)

st.markdown("""
<div class="info-card">
<b>Jak korzystać:</b><br>
• napisz: <i>zacznijmy od początku</i><br>
• albo: <i>wytłumacz receptory</i><br>
• albo wybierz pojęcie ze słowniczka po lewej
</div>
""", unsafe_allow_html=True)


for msg in st.session_state.messages:
    if msg["role"] == "user":
        with st.chat_message("user", avatar="🧑‍🎓"):
            st.markdown(msg["content"])
    else:
        with st.chat_message("assistant", avatar="🧠"):
            st.markdown(msg["content"])


user_input = st.chat_input("Napisz pytanie albo temat...")

if st.session_state.pending_prompt:
    user_input = st.session_state.pending_prompt
    st.session_state.pending_prompt = None


if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})

    with st.chat_message("user", avatar="🧑‍🎓"):
        st.markdown(user_input)

    developer_context = build_developer_context(user_input, st.session_state.level)

    with st.chat_message("assistant", avatar="🧠"):
        with st.spinner("Myślę..."):
            response = client.responses.create(
                model="gpt-5.4-mini",
                input=[
                    {"role": "system", "content": system_prompt},
                    {"role": "developer", "content": developer_context},
                    *st.session_state.messages[-8:],
                ],
            )

            answer = response.output_text
            st.markdown(answer)

    st.session_state.level = update_level(answer, st.session_state.level)
    st.session_state.messages.append({"role": "assistant", "content": answer})
    st.rerun()
