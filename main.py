import flet as ft
import sqlite3
import datetime
import os
import sys
import traceback
import time

# --- CONFIGURAÇÃO INICIAL E SEGURANÇA ---
try:
    from fpdf import FPDF
    fpdf_disponivel = True
except ImportError:
    fpdf_disponivel = False

# Variáveis globais para conexão
conn = None
cursor = None
db_path = ""

def main(page: ft.Page):
    # ==============================================================================
    # 1. TELA DE CARREGAMENTO (ANTI-TELA BRANCA)
    # ==============================================================================
    page.title = "Fitesa Mobile"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 0
    page.bgcolor = ft.Colors.GREY_50
    page.theme = ft.Theme(color_scheme_seed=ft.Colors.INDIGO, use_material3=True)

    # Status visual
    status_txt = ft.Text("Iniciando sistema...", color=ft.Colors.BLUE_GREY_400)
    loading_screen = ft.Container(
        content=ft.Column([
            ft.Icon(ft.Icons.FACTORY, size=60, color=ft.Colors.PRIMARY),
            ft.Text("Fitesa Mobile", size=24, weight="bold", color=ft.Colors.PRIMARY),
            ft.Container(height=20),
            ft.ProgressRing(),
            ft.Container(height=10),
            status_txt
        ], horizontal_alignment="center", alignment="center"),
        alignment=ft.alignment.center,
        expand=True,
        bgcolor="white"
    )

    page.add(loading_screen)
    page.update()
    time.sleep(0.5) # Tempo para o Android renderizar

    # ==============================================================================
    # 2. INICIALIZAÇÃO BLINDADA DO BANCO DE DADOS
    # ==============================================================================
    try:
        # A. Caminhos
        status_txt.value = "Verificando armazenamento..."
        page.update()
        
        rota_base = os.environ.get("HOME")
        if not rota_base:
            rota_base = os.getcwd()
        
        global db_path, conn, cursor
        db_path = os.path.join(rota_base, "fitesa_rotas.db")

        # B. Conexão
        status_txt.value = "Conectando ao banco..."
        page.update()
        
        conn = sqlite3.connect(db_path, check_same_thread=False)
        cursor = conn.cursor()
        
        # C. Tabelas
        cursor.execute("CREATE TABLE IF NOT EXISTS opcoes (id INTEGER PRIMARY KEY, tipo TEXT, nome TEXT)")
        cursor.execute("CREATE TABLE IF NOT EXISTS rotina_itens (id INTEGER PRIMARY KEY, titulo TEXT)")
        cursor.execute("CREATE TABLE IF NOT EXISTS historico (id INTEGER PRIMARY KEY, data TEXT, info TEXT)")
        cursor.execute("CREATE TABLE IF NOT EXISTS rascunho (id TEXT PRIMARY KEY, valor TEXT)")
        
        # Migração segura (coluna ordem)
        try:
            cursor.execute("SELECT ordem FROM rotina_itens LIMIT 1")
        except sqlite3.OperationalError:
            cursor.execute("ALTER TABLE rotina_itens ADD COLUMN ordem INTEGER DEFAULT 0")
            conn.commit()
            
        conn.commit()
        status_txt.value = "Sistema carregado!"
        page.update()
        time.sleep(0.5)

    except Exception as e:
        # TELA DE ERRO (EM VEZ DE TELA BRANCA)
        page.clean()
        page.add(ft.Container(
            content=ft.Column([
                ft.Icon(ft.Icons.ERROR_OUTLINE, color="red", size=60),
                ft.Text("Falha na Inicialização", size=20, weight="bold"),
                ft.Text(str(e), color="red"),
                ft.Text(traceback.format_exc(), size=10, font_family="monospace")
            ]),
            padding=30, alignment=ft.alignment.center
        ))
        page.update()
        return

    # ==============================================================================
    # 3. APLICAÇÃO COMPLETA (FUNCIONALIDADES RESTAURADAS)
    # ==============================================================================
    
    # Variáveis de Estado
    user_data = {"fotos": {}}
    current_nav_index = 0

    # --- Helpers de Banco de Dados ---
    def save_draft(key, value):
        try:
            if conn:
                conn.cursor().execute("INSERT OR REPLACE INTO rascunho (id, valor) VALUES (?, ?)", (key, str(value)))
                conn.commit()
        except: pass

    def get_draft(key):
        try:
            if conn:
                res = conn.cursor().execute("SELECT valor FROM rascunho WHERE id = ?", (key,)).fetchone()
                return res[0] if res else ""
            return ""
        except: return ""

    # --- Componentes Visuais ---
    def criar_card(titulo, conteudo, icone=None):
        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(icone, color=ft.Colors.PRIMARY, size=20) if icone else ft.Container(),
                    ft.Text(titulo, weight="bold", size=16, color=ft.Colors.PRIMARY),
                ], spacing=10),
                ft.Divider(height=10, color="transparent"),
                conteudo
            ], spacing=5),
            bgcolor="white",
            padding=20,
            border_radius=15,
            shadow=ft.BoxShadow(spread_radius=1, blur_radius=10, color=ft.Colors.BLUE_GREY_50, offset=ft.Offset(0, 4)),
            margin=ft.margin.only(bottom=15, left=15, right=15)
        )

    # --- Inputs Globais ---
    date_picker = ft.DatePicker(
        first_date=datetime.datetime(2023, 1, 1),
        last_date=datetime.datetime(2030, 12, 31),
    )
    page.overlay.append(date_picker) # Adiciona Overlay com segurança

    txt_data = ft.TextField(
        label="Data", 
        read_only=True, 
        prefix_icon=ft.Icons.CALENDAR_MONTH, 
        border_radius=10,
        value=get_draft("data") or datetime.datetime.now().strftime("%d/%m/%Y")
    )
    
    def on_date_change(e):
        if date_picker.value:
            txt_data.value = date_picker.value.strftime("%d/%m/%Y")
            save_draft("data", txt_data.value)
            page.update()
    date_picker.on_change = on_date_change
    txt_data.on_focus = lambda _: date_picker.pick_date()

    dd_lider = ft.Dropdown(label="Líder", border_radius=10, expand=True, on_change=lambda e: save_draft("lider", e.control.value))
    dd_maquina = ft.Dropdown(label="Máquina", border_radius=10, expand=True, on_change=lambda e: save_draft("maquina", e.control.value))
    dd_turma = ft.Dropdown(label="Turma", border_radius=10, expand=True, on_change=lambda e: save_draft("turma", e.control.value))
    dd_rota = ft.Dropdown(label="Rota", border_radius=10, expand=True, on_change=lambda e: save_draft("rota", e.control.value))

    # --- Câmera ---
    def on_file_result(e: ft.FilePickerResultEvent):
        if e.files:
            secao = page.session.get("current_section")
            if secao:
                user_data["fotos"][secao] = e.files[0].path
                page.snack_bar = ft.SnackBar(ft.Text(f"Foto salva!"), bgcolor="green")
                page.open(page.snack_bar)
                page.update()
    
    file_picker = ft.FilePicker(on_result=on_file_result)
    page.overlay.append(file_picker)

    # --- PDF ---
    def gerar_pdf(e):
        if not fpdf_disponivel:
            page.snack_bar = ft.SnackBar(ft.Text("Erro: Biblioteca FPDF ausente"), bgcolor="red")
            page.open(page.snack_bar)
            return
        
        try:
            from fpdf import FPDF
            pdf = FPDF()
            pdf.add_page()
            
            pdf.set_font("Arial", 'B', 16)
            pdf.cell(0, 10, txt="RELATORIO DE ROTA FITESA", ln=True, align='C')
            pdf.set_font("Arial", size=12)
            pdf.ln(5)
            
            pdf.cell(0, 10, txt=f"Data: {txt_data.value}", ln=True)
            pdf.cell(0, 10, txt=f"Lider: {dd_lider.value} | Turma: {dd_turma.value}", ln=True)
            pdf.cell(0, 10, txt=f"Maquina: {dd_maquina.value} | Rota: {dd_rota.value}", ln=True)
            pdf.ln(5)
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            pdf.ln(5)
            
            c = conn.cursor()
            itens = c.execute("SELECT titulo FROM rotina_itens ORDER BY ordem ASC, id ASC").fetchall()
            
            if not itens:
                pdf.cell(0, 10, txt="Nenhum item cadastrado.", ln=True)
            else:
                for item in itens:
                    t = item[0]
                    obs = get_draft(f"obs_{t}")
                    pdf.set_font("Arial", 'B', 12)
                    pdf.cell(0, 8, txt=f"- {t}", ln=True)
                    if obs:
                        pdf.set_font("Arial", size=11)
                        pdf.multi_cell(0, 6, txt=f"  Obs: {obs}")
                    else:
                        pdf.set_font("Arial", 'I', 10)
                        pdf.cell(0, 6, txt="  (Sem observacoes)", ln=True)
                    pdf.ln(2)

            nome_arq = f"{txt_data.value.replace('/', '_')}_{dd_turma.value}.pdf"
            caminho_final = os.path.join(os.path.dirname(db_path), nome_arq)
            
            pdf.output(caminho_final)
            conn.cursor().execute("INSERT INTO historico (data, info) VALUES (?, ?)", (txt_data.value, nome_arq))
            conn.commit()
            
            page.snack_bar = ft.SnackBar(ft.Text(f"Salvo em: {caminho_final}"), bgcolor="green")
            page.open(page.snack_bar)
            page.update()
        except Exception as ex:
            page.snack_bar = ft.SnackBar(ft.Text(f"Erro PDF: {ex}"), bgcolor="red")
            page.open(page.snack_bar)
            page.update()

    # --- ADMINISTRAÇÃO (COM DRAG & DROP E ABAS) ---
    def show_admin(e=None):
        nonlocal current_nav_index
        current_nav_index = 2
        page.clean()
        page.navigation_bar.selected_index = 2
        page.navigation_bar.visible = True

        novo_item_input = ft.TextField(label="Novo Item...", expand=True, border_radius=10)
        tipo_item_dd = ft.Dropdown(label="Categoria", width=120, border_radius=10, options=[
            ft.dropdown.Option("lider", "Líder"), ft.dropdown.Option("maquina", "Máq."),
            ft.dropdown.Option("turma", "Turma"), ft.dropdown.Option("rota", "Rota"),
            ft.dropdown.Option("rotina", "Checklist")
        ], value="rotina")

        def cadastrar(e):
            if not novo_item_input.value or not tipo_item_dd.value: return
            local_c = conn.cursor()
            if tipo_item_dd.value == "rotina":
                res = local_c.execute("SELECT MAX(ordem) FROM rotina_itens").fetchone()
                ordem = (res[0] or 0) + 1
                local_c.execute("INSERT INTO rotina_itens (titulo, ordem) VALUES (?, ?)", (novo_item_input.value, ordem))
            else:
                local_c.execute("INSERT INTO opcoes (tipo, nome) VALUES (?, ?)", (tipo_item_dd.value, novo_item_input.value))
            conn.commit()
            novo_item_input.value = ""
            page.snack_bar = ft.SnackBar(ft.Text("Item adicionado!"), bgcolor="green")
            page.open(page.snack_bar)
            show_admin()

        def deletar(tabela, id_item):
            conn.cursor().execute(f"DELETE FROM {tabela} WHERE id=?", (id_item,))
            conn.commit()
            show_admin()

        # Drag and Drop Logic
        def drag_accept(e):
            try:
                src_id = int(e.data)
                tgt_id = int(e.control.data)
            except: return
            if src_id == tgt_id: return
            
            local_c = conn.cursor()
            rows = local_c.execute("SELECT id FROM rotina_itens ORDER BY ordem ASC").fetchall()
            ids = [r[0] for r in rows]
            
            if src_id in ids and tgt_id in ids:
                ids.remove(src_id)
                insert_idx = ids.index(tgt_id)
                ids.insert(insert_idx, src_id)
                for idx, i_id in enumerate(ids):
                    local_c.execute("UPDATE rotina_itens SET ordem = ? WHERE id = ?", (idx, i_id))
                conn.commit()
                show_admin()

        def criar_lista(tipo):
            if tipo == "rotina":
                col = ft.Column(spacing=5)
                for r in conn.cursor().execute("SELECT id, titulo FROM rotina_itens ORDER BY ordem ASC").fetchall():
                    item_id, txt = r[0], r[1]
                    card = ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.Icons.DRAG_INDICATOR, color="grey"),
                            ft.Text(txt, expand=True),
                            ft.IconButton(ft.Icons.DELETE, icon_color="red", on_click=lambda e, i=item_id: deletar("rotina_itens", i))
                        ]),
                        bgcolor="white", padding=10, border_radius=8, border=ft.border.all(1, ft.Colors.GREY_200)
                    )
                    draggable = ft.Draggable(group="g", content=card, content_when_dragging=ft.Container(content=card, opacity=0.5), data=item_id)
                    target = ft.DragTarget(group="g", content=draggable, on_accept=drag_accept, data=item_id)
                    col.controls.append(target)
                return col
            else:
                col = ft.Column(spacing=5)
                for r in conn.cursor().execute(f"SELECT id, nome FROM opcoes WHERE tipo='{tipo}'").fetchall():
                    col.controls.append(ft.Container(
                        content=ft.Row([
                            ft.Text(r[1], expand=True),
                            ft.IconButton(ft.Icons.DELETE, icon_color="red", on_click=lambda e, i=r[0]: deletar("opcoes", i))
                        ]),
                        bgcolor="white", padding=10, border_radius=8, border=ft.border.all(1, ft.Colors.GREY_200)
                    ))
                return col

        tabs = ft.Tabs(
            selected_index=4, # Começa na rotina
            animation_duration=300,
            tabs=[
                ft.Tab(text="Líder", content=criar_lista("lider")),
                ft.Tab(text="Máq.", content=criar_lista("maquina")),
                ft.Tab(text="Turma", content=criar_lista("turma")),
                ft.Tab(text="Rota", content=criar_lista("rota")),
                ft.Tab(text="Rotina", content=criar_lista("rotina")),
            ],
            expand=True
        )

        page.add(
            ft.Container(content=ft.Text("Administração", size=20, weight="bold", color="white"), bgcolor=ft.Colors.PRIMARY, padding=ft.padding.only(left=20, right=20, top=50, bottom=20)),
            ft.Container(content=ft.Column([
                ft.Row([novo_item_input, tipo_item_dd]),
                ft.ElevatedButton("Adicionar", on_click=cadastrar, width=page.width, style=ft.ButtonStyle(bgcolor=ft.Colors.PRIMARY, color="white")),
                ft.Divider(),
                tabs
            ]), padding=20, expand=True)
        )
        page.update()

    def check_admin_pass(e=None):
        pw = ft.TextField(label="Senha", password=True, text_align="center")
        def validar(e):
            if pw.value == "production26":
                dlg.open = False
                page.update()
                show_admin()
            else:
                pw.error_text = "Senha Incorreta"
                page.update()
        dlg = ft.AlertDialog(title=ft.Text("Acesso Restrito"), content=pw, actions=[ft.TextButton("Entrar", on_click=validar)])
        page.open(dlg)

    # --- TELA DA ROTA (PRINCIPAL) ---
    def show_rota(e=None):
        nonlocal current_nav_index
        current_nav_index = 1
        page.clean()
        page.navigation_bar.selected_index = 1
        page.navigation_bar.visible = True

        try:
            c = conn.cursor()
            dd_lider.options = [ft.dropdown.Option(r[0]) for r in c.execute("SELECT nome FROM opcoes WHERE tipo='lider'").fetchall()]
            dd_maquina.options = [ft.dropdown.Option(r[0]) for r in c.execute("SELECT nome FROM opcoes WHERE tipo='maquina'").fetchall()]
            dd_turma.options = [ft.dropdown.Option(r[0]) for r in c.execute("SELECT nome FROM opcoes WHERE tipo='turma'").fetchall()]
            dd_rota.options = [ft.dropdown.Option(r[0]) for r in c.execute("SELECT nome FROM opcoes WHERE tipo='rota'").fetchall()]
            
            # Recuperar valores
            dd_lider.value = get_draft("lider")
            dd_maquina.value = get_draft("maquina")
            dd_turma.value = get_draft("turma")
            dd_rota.value = get_draft("rota")

            lista_itens = ft.Column(spacing=15)
            for r in c.execute("SELECT titulo FROM rotina_itens ORDER BY ordem ASC").fetchall():
                t = r[0]
                lista_itens.controls.append(ft.Container(
                    content=ft.Column([
                        ft.Row([ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE, color="grey"), ft.Text(t, weight="w500", size=15)]),
                        ft.Row([
                            ft.IconButton(ft.Icons.CAMERA_ALT, icon_color=ft.Colors.PRIMARY, on_click=lambda e, x=t: (page.session.set("current_section", x), file_picker.pick_files(capture=True))),
                            ft.TextField(hint_text="Obs...", expand=True, text_size=13, on_change=lambda e, x=t: save_draft(f"obs_{x}", e.control.value), value=get_draft(f"obs_{t}"))
                        ])
                    ]),
                    bgcolor="white", padding=15, border_radius=10, border=ft.border.all(1, ft.Colors.GREY_200)
                ))

        except Exception as e:
            page.add(ft.Text(f"Erro rota: {e}", color="red"))
            return

        def limpar(e):
            conn.cursor().execute("DELETE FROM rascunho")
            conn.commit()
            show_rota()

        page.add(
            ft.Container(
                content=ft.Row([ft.Text("Nova Rota", size=20, weight="bold"), ft.Icon(ft.Icons.ASSIGNMENT, color=ft.Colors.PRIMARY)], alignment="spaceBetween"),
                padding=ft.padding.only(left=20, right=20, top=40, bottom=10), bgcolor="white"
            ),
            ft.Column([
                criar_card("1. Identificação", ft.Column([txt_data, dd_lider, dd_maquina, dd_turma, dd_rota]), icone=ft.Icons.PERSON_SEARCH),
                ft.Container(content=ft.Text("2. Checklist", weight="bold", size=16, color=ft.Colors.PRIMARY), padding=ft.padding.only(left=25)),
                ft.Container(content=lista_itens, padding=ft.padding.only(left=15, right=15)),
                ft.Container(content=ft.Column([
                    ft.ElevatedButton("Limpar", icon=ft.Icons.CLEANING_SERVICES, on_click=limpar, bgcolor=ft.Colors.RED_400, color="white", width=page.width),
                    ft.Container(height=10),
                    ft.ElevatedButton("Finalizar PDF", icon=ft.Icons.PICTURE_AS_PDF, on_click=gerar_pdf, bgcolor=ft.Colors.GREEN, color="white", width=page.width)
                ]), padding=20),
                ft.Container(height=80)
            ], scroll="auto", expand=True)
        )
        page.update()

    # --- MENU INICIAL ---
    def show_menu():
        nonlocal current_nav_index
        current_nav_index = 0
        page.clean()
        page.navigation_bar.selected_index = 0
        page.navigation_bar.visible = True
        
        page.add(
            ft.Column([
                ft.Container(
                    content=ft.Column([ft.Text("Olá, Lider", size=28, weight="bold", color="white"), ft.Text("Tenha uma ótima rota!", color="white70")]),
                    bgcolor=ft.Colors.PRIMARY, padding=ft.padding.only(left=20, right=20, top=60, bottom=30),
                    border_radius=ft.border_radius.only(bottom_left=30, bottom_right=30)
                ),
                ft.Container(content=ft.Row([
                    ft.Container(content=ft.Column([ft.Icon(ft.Icons.PLAY_CIRCLE_FILL, size=50, color=ft.Colors.PRIMARY), ft.Text("Iniciar", weight="bold")]), 
                                 bgcolor="white", padding=20, border_radius=20, on_click=lambda _: show_rota(), expand=True, shadow=ft.BoxShadow(blur_radius=10, color=ft.Colors.GREY_200)),
                    ft.Container(content=ft.Column([ft.Icon(ft.Icons.SETTINGS, size=50, color=ft.Colors.ORANGE), ft.Text("Config", weight="bold")]), 
                                 bgcolor="white", padding=20, border_radius=20, on_click=lambda _: check_admin_pass(), expand=True, shadow=ft.BoxShadow(blur_radius=10, color=ft.Colors.GREY_200))
                ], spacing=20), padding=20, margin=ft.margin.only(top=-20))
            ])
        )
        page.update()

    # --- NAVEGAÇÃO E LOGIN ---
    def on_nav(e):
        idx = e.control.selected_index
        if idx == 0: show_menu()
        elif idx == 1: show_rota()
        elif idx == 2: check_admin_pass()

    page.navigation_bar = ft.NavigationBar(
        destinations=[
            ft.NavigationBarDestination(icon=ft.Icons.HOME, label="Início"),
            ft.NavigationBarDestination(icon=ft.Icons.ASSIGNMENT, label="Rota"),
            ft.NavigationBarDestination(icon=ft.Icons.ADMIN_PANEL_SETTINGS, label="Admin"),
        ],
        on_change=on_nav,
        visible=False,
        bgcolor="white",
        elevation=10
    )

    def show_login():
        page.clean()
        page.navigation_bar.visible = False
        user = ft.TextField(label="Usuário", prefix_icon=ft.Icons.PERSON)
        pw = ft.TextField(label="Senha", password=True, prefix_icon=ft.Icons.LOCK)
        
        def entrar(e):
            if (user.value == "lider" and pw.value == "123") or (user.value == "admin" and pw.value == "admin"):
                show_menu()
            else:
                page.snack_bar = ft.SnackBar(ft.Text("Erro de login"), bgcolor="red")
                page.open(page.snack_bar)

        page.add(
            ft.Container(content=ft.Column([
                ft.Icon(ft.Icons.FACTORY, size=80, color=ft.Colors.PRIMARY),
                ft.Text("Fitesa", size=30, weight="bold", color=ft.Colors.PRIMARY),
                ft.Divider(height=40, color="transparent"),
                user, pw,
                ft.ElevatedButton("ACESSAR", on_click=entrar, width=300, height=50, style=ft.ButtonStyle(bgcolor=ft.Colors.PRIMARY, color="white"))
            ], horizontal_alignment="center"), alignment=ft.alignment.center, expand=True, padding=40)
        )

    # Início do Fluxo Principal (Após carregamento seguro)
    show_login()

ft.app(target=main)
