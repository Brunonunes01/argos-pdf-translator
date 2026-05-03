from __future__ import annotations

from pathlib import Path
import os

import streamlit as st

from src.bilingual_service import BilingualService
from src.config import load_environment


st.set_page_config(page_title="PDF Bilingual Book Generator", layout="wide")
load_environment()

st.markdown(
    """
    <style>
      .block-container {
        max-width: 1280px;
        padding-top: 1.5rem;
        padding-bottom: 3rem;
      }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def get_service(cache_version: str) -> BilingualService:
    return BilingualService()


def store_log(message: str) -> None:
    st.session_state.setdefault("logs", []).append(message)


def read_file(path: Path) -> bytes:
    return path.read_bytes()


def render_export_section(
    service: BilingualService,
    book,
    preview_start_page: int,
    preview_end_page: int,
) -> None:
    st.subheader("Exportacao")
    preview_chunks = service.get_preview(book.id, preview_start_page, preview_end_page)
    has_interval_content = bool(preview_chunks)
    translated_bounds = service.get_translated_page_bounds(book.id)
    if translated_bounds:
        st.caption(f"Paginas traduzidas disponiveis para consolidar: {translated_bounds[0]} a {translated_bounds[1]}.")
    else:
        st.caption("Nenhuma pagina traduzida ainda para consolidar.")
    if not has_interval_content:
        st.caption("O intervalo atual ainda nao tem texto processado para exportar.")

    col_html, col_pdf, col_full = st.columns(3)

    with col_html:
        if st.button("Gerar HTML do intervalo", disabled=not has_interval_content):
            try:
                html_path = service.export_html(book, preview_start_page, preview_end_page)
                st.session_state.html_path = str(html_path)
                st.success(f"HTML gerado: {html_path}")
            except Exception as exc:
                st.error(f"Falha ao gerar HTML: {exc}")
        if "html_path" in st.session_state:
            html_path = Path(st.session_state.html_path)
            if html_path.exists():
                st.download_button(
                    "Baixar HTML",
                    data=read_file(html_path),
                    file_name=html_path.name,
                    mime="text/html",
                )

    with col_pdf:
        if st.button("Gerar PDF do intervalo", disabled=not has_interval_content):
            try:
                pdf_output_path = service.export_pdf(book, preview_start_page, preview_end_page)
                st.session_state.pdf_output_path = str(pdf_output_path)
                st.success(f"PDF gerado: {pdf_output_path}")
            except Exception as exc:
                st.error(f"Falha ao gerar PDF: {exc}")
        if "pdf_output_path" in st.session_state:
            pdf_output_path = Path(st.session_state.pdf_output_path)
            if pdf_output_path.exists():
                st.download_button(
                    "Baixar PDF",
                    data=read_file(pdf_output_path),
                    file_name=pdf_output_path.name,
                    mime="application/pdf",
                )

    with col_full:
        if st.button("Gerar PDF consolidado", disabled=translated_bounds is None):
            try:
                assert translated_bounds is not None
                pdf_full_path = service.export_pdf(book, translated_bounds[0], translated_bounds[1])
                st.session_state.pdf_full_path = str(pdf_full_path)
                st.success(f"PDF consolidado gerado: {pdf_full_path}")
            except Exception as exc:
                st.error(f"Falha ao gerar PDF consolidado: {exc}")
        if "pdf_full_path" in st.session_state:
            pdf_full_path = Path(st.session_state.pdf_full_path)
            if pdf_full_path.exists():
                st.download_button(
                    "Baixar PDF consolidado",
                    data=read_file(pdf_full_path),
                    file_name=pdf_full_path.name,
                    mime="application/pdf",
                )


service = get_service("argos-ui-safe-v1")
has_openai_key = bool(os.getenv("OPENAI_API_KEY"))
has_gemini_key = bool(os.getenv("GEMINI_API_KEY"))

st.title("PDF Bilingual Book Generator")
st.caption("Traducao local com Argos, OCR para PDFs escaneados e exportacao bilingue para estudo.")

if "logs" not in st.session_state:
    st.session_state.logs = []
if "active_start_page" not in st.session_state:
    st.session_state.active_start_page = 1
if "active_end_page" not in st.session_state:
    st.session_state.active_end_page = 1
if "auto_run" not in st.session_state:
    st.session_state.auto_run = False
if "flash_message" in st.session_state:
    st.info(st.session_state.pop("flash_message"))

with st.sidebar:
    st.header("Arquivo")
    uploaded_file = st.file_uploader("Selecione um PDF", type=["pdf"])
    st.caption("PDFs com texto embutido sao processados diretamente. PDFs escaneados usam OCR quando Tesseract esta instalado.")

book = None
pdf_path = None

if uploaded_file:
    try:
        book, pdf_path = service.register_upload(uploaded_file)
        previous_book_id = getattr(st.session_state.get("book"), "id", None)
        if previous_book_id != book.id:
            st.session_state.active_start_page = 1
            st.session_state.active_end_page = 1
            for key in ["html_path", "pdf_output_path", "pdf_full_path"]:
                st.session_state.pop(key, None)
        st.session_state.book = book
        st.session_state.pdf_path = str(pdf_path)
    except Exception as exc:
        st.error(f"Nao foi possivel carregar o PDF: {exc}")

if "book" in st.session_state and "pdf_path" in st.session_state:
    book = st.session_state.book
    pdf_path = Path(st.session_state.pdf_path)

if not book or not pdf_path:
    st.info("Suba um arquivo PDF para comecar.")
    st.stop()

progress = service.get_progress(book.id)
preview_start_page = int(st.session_state.get("active_start_page", 1))
preview_end_page = int(st.session_state.get("active_end_page", 1))

st.subheader("Livro")
col_a, col_b, col_c, col_d = st.columns(4)
display_name = book.filename if len(book.filename) <= 44 else f"{book.filename[:41]}..."
col_a.metric("Arquivo", display_name)
col_b.metric("Paginas", book.total_pages)
col_c.metric("Chunks traduzidos", progress["translated_chunks"])
col_d.metric("Paginas com traducao", progress["translated_pages"])

with st.expander("Escolher paginas da previa/exportacao", expanded=False):
    view_col_start, view_col_end = st.columns(2)
    selected_preview_start = view_col_start.number_input(
        "Pagina inicial da previa",
        min_value=1,
        max_value=book.total_pages,
        value=min(max(preview_start_page, 1), book.total_pages),
        step=1,
    )
    selected_preview_end = view_col_end.number_input(
        "Pagina final da previa",
        min_value=1,
        max_value=book.total_pages,
        value=min(max(preview_end_page, int(selected_preview_start)), book.total_pages),
        step=1,
    )
    if int(selected_preview_start) <= int(selected_preview_end):
        preview_start_page = int(selected_preview_start)
        preview_end_page = int(selected_preview_end)
        st.session_state.active_start_page = preview_start_page
        st.session_state.active_end_page = preview_end_page
    else:
        st.warning("A pagina inicial da previa nao pode ser maior que a final.")

st.divider()
render_export_section(service, book, preview_start_page, preview_end_page)

st.divider()

st.subheader("Processamento")
translator_options = ["Mock (teste - nao traduz)"]
translator_options.insert(0, "Argos")
with st.expander("Tradutores via API"):
    st.caption("Argos e o tradutor principal local. Gemini/OpenAI ficam disponiveis apenas se voce quiser comparar depois.")
    use_api_translators = st.checkbox("Mostrar Gemini/OpenAI", value=False)

if use_api_translators:
    if has_gemini_key:
        translator_options.append("Gemini")
    else:
        translator_options.append("Gemini")
    if has_openai_key:
        translator_options.append("OpenAI")
    else:
        translator_options.append("OpenAI")

target_default = book.total_pages
col_goal, col_batch, col_translator = st.columns([1, 1, 1])
target_page = col_goal.number_input(
    "Traduzir ate a pagina",
    min_value=1,
    max_value=book.total_pages,
    value=target_default,
    step=1,
)
batch_size = col_batch.number_input("Paginas por rodada", min_value=1, max_value=50, value=5, step=1)
translator_label = col_translator.selectbox(
    "Tradutor",
    translator_options,
    index=0,
)
translator_name = "Mock" if translator_label.startswith("Mock") else translator_label

pt_to_en = False
if translator_name == "Argos":
    pt_to_en = st.toggle("Traduzir portugues -> ingles", value=False)

source_lang = "pt-BR" if pt_to_en else "en"
target_lang = "en" if pt_to_en else "pt-BR"
source_label = "PT" if pt_to_en else "EN"
target_label = "EN" if pt_to_en else "PT"

batch_summary = service.get_batch_summary(book, int(target_page))
next_batch = service.get_next_batch_range(book, int(batch_size), int(target_page))
if next_batch:
    done_col, pending_col, range_col, target_col, fail_col = st.columns([1, 1, 1, 1, 1])
    done_col.metric("Ultima pagina concluida", batch_summary["last_completed"] or 0)
    pending_col.metric("Primeira incompleta", batch_summary["first_pending"] or "-")
    range_col.metric("Rodada atual", f"Paginas {next_batch[0]} a {next_batch[1]}")
    target_col.metric("Meta", f"Ate pagina {int(target_page)}")
    fail_col.metric("Chunks com falha", batch_summary["failed_chunks"] or 0)
    if batch_summary["first_pending_failed"]:
        st.warning(
            "A rodada atual volta na primeira pagina incompleta porque existem chunks com falha. "
            "Isso evita deixar buracos no PDF final."
        )
        st.caption("Quando essa pagina ficar completa, a proxima rodada avanca para as paginas seguintes.")
    else:
        st.caption(
            "A rodada atual comeca na primeira pagina ainda nao concluida. "
            "Ao terminar, o app recalcula automaticamente o proximo intervalo."
        )
else:
    st.success(f"Traducao concluida ate a pagina {int(target_page)}.")
    st.info("Proximo passo: use o botao Gerar PDF consolidado na area de Exportacao acima.")

if book.total_pages > 50:
    st.info(
        "Para livros grandes, processe em rodadas. O app salva o progresso no cache e continua da primeira pagina incompleta."
    )

if translator_name == "Mock":
    st.info(
        "O modo Mock nao traduz de verdade. Ele repete o texto original para testar upload, "
        "extracao, cache, previa e exportacao. Para traducao real, use Argos local ou configure "
        "Gemini/OpenAI no arquivo .env e selecione o tradutor correspondente."
    )
else:
    st.info(
        "Se este intervalo foi processado antes com Mock, esses chunks serao retraduzidos "
        "automaticamente com o tradutor real selecionado."
    )

if translator_name == "OpenAI" and not has_openai_key:
    st.warning("OpenAI selecionado, mas OPENAI_API_KEY nao esta configurada no arquivo .env.")

if translator_name == "Gemini" and not has_gemini_key:
    st.warning("Gemini selecionado, mas GEMINI_API_KEY nao esta configurada no arquivo .env.")

if translator_name == "Argos":
    st.caption(
        "Argos roda localmente/offline depois que o pacote de idioma ingles->portugues for instalado. "
        "Na primeira execucao, o app tenta baixar esse pacote automaticamente."
    )

button_col_1, button_col_2, button_col_3 = st.columns([1, 1, 1])
continue_button = button_col_1.button(
    "Processar proxima rodada",
    type="primary",
    disabled=next_batch is None or st.session_state.auto_run,
    use_container_width=True,
)
auto_button = button_col_2.button(
    "Automatico: iniciar",
    disabled=next_batch is None or st.session_state.auto_run,
    use_container_width=True,
)
stop_auto_button = button_col_3.button(
    "Parar automatico",
    disabled=not st.session_state.auto_run,
    use_container_width=True,
)
progress_bar = st.progress(0)
live_status = st.empty()

selected_start_page = next_batch[0] if next_batch else 1
selected_end_page = next_batch[1] if next_batch else 1

with st.expander("Modo avancado: processar intervalo manual"):
    default_end = min(book.total_pages, 3)
    manual_col_1, manual_col_2, manual_col_3 = st.columns([1, 1, 1])
    manual_start_page = manual_col_1.number_input(
        "Pagina inicial manual",
        min_value=1,
        max_value=book.total_pages,
        value=1,
        step=1,
    )
    manual_end_page = manual_col_2.number_input(
        "Pagina final manual",
        min_value=1,
        max_value=book.total_pages,
        value=default_end,
        step=1,
    )
    reprocess = manual_col_3.checkbox("Reprocessar intervalo", value=False)
    manual_button = st.button("Processar intervalo manual")

if manual_button:
    selected_start_page = int(manual_start_page)
    selected_end_page = int(manual_end_page)
    selected_reprocess = reprocess
elif continue_button and next_batch:
    selected_start_page, selected_end_page = next_batch
    selected_reprocess = False
else:
    selected_reprocess = False

if auto_button:
    st.session_state.logs = []
    st.session_state.auto_run = True

if stop_auto_button:
    st.session_state.auto_run = False
    st.session_state.flash_message = "Automatico pausado pelo usuario."
    st.rerun()

if st.session_state.auto_run:
    st.session_state.logs = []
    st.info(f"Automatico ligado: processando uma pagina por ciclo ate a pagina {int(target_page)}.")
    try:
        current_batch = service.get_next_batch_range(book, 1, int(target_page))
        if not current_batch:
            st.session_state.auto_run = False
            st.session_state.flash_message = f"Traducao concluida ate a pagina {int(target_page)}."
            st.rerun()

        page_to_process = current_batch[0]
        st.session_state.active_start_page = page_to_process
        st.session_state.active_end_page = page_to_process
        page_logs: list[str] = []
        live_status.info(f"Traduzindo pagina {page_to_process}.")

        def log_auto(message: str) -> None:
            store_log(message)
            page_logs.append(message)
            live_status.info(message)

        service.process_pages(
            book=book,
            pdf_path=pdf_path,
            start_page=page_to_process,
            end_page=page_to_process,
            translator_name=translator_name,
            source_lang=source_lang,
            target_lang=target_lang,
            reprocess=False,
            log=log_auto,
            progress=None,
        )

        has_failure = any("Falha" in line or "Quota" in line for line in page_logs)
        if has_failure:
            st.session_state.auto_run = False
            st.session_state.flash_message = (
                f"Rodada pausada na pagina {page_to_process}. "
                "Limpe ou reprocesse os chunks com falha para continuar."
            )
        else:
            st.session_state.flash_message = (
                f"Pagina {page_to_process} processada. Automatico continuando ate a pagina {int(target_page)}."
            )
        st.rerun()
    except ValueError as exc:
        st.session_state.auto_run = False
        st.warning(str(exc))
    except Exception as exc:
        st.session_state.auto_run = False
        st.error(f"Falha no processamento automatico: {exc}")

if continue_button or manual_button:
    st.session_state.logs = []
    st.session_state.active_start_page = selected_start_page
    st.session_state.active_end_page = selected_end_page
    st.info(f"Traduzindo agora: paginas {selected_start_page} a {selected_end_page}.")
    try:
        total_to_translate = {"value": 0}

        def log_progress(message: str) -> None:
            store_log(message)
            live_status.info(message)

        def update_progress(done: int, total: int) -> None:
            total_to_translate["value"] = total
            progress_bar.progress(1.0 if total == 0 else done / total)

        chunks = service.process_pages(
            book=book,
            pdf_path=pdf_path,
            start_page=selected_start_page,
            end_page=selected_end_page,
            translator_name=translator_name,
            source_lang=source_lang,
            target_lang=target_lang,
            reprocess=selected_reprocess,
            log=log_progress,
            progress=update_progress,
        )
        if not chunks:
            st.warning(
                "Este PDF parece ser escaneado ou baseado em imagem. "
                "A extracao de texto retornou pouco ou nenhum conteudo. "
                "Uma versao futura pode usar OCR."
            )
        else:
            st.session_state.flash_message = (
                f"Rodada finalizada: paginas {selected_start_page} a {selected_end_page}. "
                "Status atualizado abaixo."
            )
            st.rerun()
    except ValueError as exc:
        st.warning(str(exc))
    except Exception as exc:
        st.error(f"Falha no processamento: {exc}")

if st.session_state.logs:
    with st.expander("Logs do processamento", expanded=True):
        for line in st.session_state.logs:
            st.write(line)

with st.expander("Manutencao do cache"):
    st.write("Use isto se algum texto antigo do modo Mock continuar aparecendo na previa.")
    if st.button("Limpar traducoes Mock salvas"):
        reset_count = service.db.reset_all_mock_translations()
        st.success(f"{reset_count} chunks Mock foram limpos. Processe novamente com Argos.")
    if st.button("Limpar chunks com falha"):
        reset_count = service.db.reset_failed_chunks()
        st.success(f"{reset_count} chunks com falha foram marcados como pendentes novamente.")
    if st.button("Limpar paginas vazias deste livro"):
        reset_count = service.db.reset_empty_pages(book.id)
        st.success(f"{reset_count} paginas vazias foram liberadas para reprocessamento.")
    st.divider()
    st.warning("Reset total apaga livros cadastrados, chunks, traducoes e progresso salvo no SQLite.")
    confirm_reset = st.checkbox("Confirmo que quero zerar o banco e recomecar do zero")
    if st.button("Zerar banco", disabled=not confirm_reset):
        service.db.reset_all_data()
        for key in [
            "book",
            "pdf_path",
            "logs",
            "active_start_page",
            "active_end_page",
            "html_path",
            "pdf_output_path",
            "pdf_full_path",
        ]:
            st.session_state.pop(key, None)
        st.success("Banco zerado. Recarregue a pagina e suba o PDF novamente.")
        st.rerun()

st.divider()

st.subheader("Previa bilingue")
st.caption(f"Intervalo em exibicao: paginas {preview_start_page} a {preview_end_page}.")
try:
    preview_chunks = service.get_preview(book.id, preview_start_page, preview_end_page)
except Exception:
    preview_chunks = []

if not preview_chunks:
    st.info("Nenhum chunk processado neste intervalo ainda.")
else:
    current_page = None
    for chunk in preview_chunks:
        if chunk.page_number != current_page:
            current_page = chunk.page_number
            st.markdown(f"### Pagina {current_page}")
        with st.container(border=True):
            st.markdown(f"**Original ({source_label})**")
            st.write(chunk.original_text)
            st.markdown(f"**Traducao ({target_label})**")
            if chunk.status == "failed":
                st.warning("Traducao pendente: falhou temporariamente. Tente processar novamente depois.")
            else:
                st.info(chunk.translated_text or "[Traducao pendente]")
