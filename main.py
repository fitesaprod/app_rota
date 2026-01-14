import flet as ft
import sqlite3
import datetime
import os
from fpdf import FPDF

# --- CONFIGURAÇÃO DO BANCO DE DADOS ---
def init_db():
    conn = sqlite3.connect("fitesa_rotas.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS opcoes (id INTEGER PRIMARY KEY, tipo TEXT, nome TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS rotina_itens (id INTEGER PRIMARY KEY, titulo TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS historico (id INTEGER PRIMARY KEY, data TEXT, info TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS rascunho (id TEXT PRIMARY KEY, valor TEXT)")
    conn.commit()
    return conn

conn = init_db()

def main(page: ft.Page):
    page.title = "Sistema de Rotas Fitesa"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.scroll = "auto"
    page.padding = 0

    # --- VARIÁVEIS DE ESTADO ---
    user_data = {"fotos": {}}
    current_nav_index = 0 

    # --- FUNÇÕES AUXILIARES ---
    def save_draft(key, value):
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO rascunho (id, valor) VALUES (?, ?)", (key, value))
        conn.commit()

    def get_draft(key):
        res = conn.cursor().execute("SELECT valor FROM rascunho WHERE id = ?", (key,)).fetchone()
        return res[0] if res else ""

    def container_campo(control):
        return ft.Container(
            content=control,
            padding=ft.padding.only(left=10, right=10, top=5, bottom=5),
            width=page.width
        )

    # --- COMPONENTES DE DATA ---
    def on_date_change(e):
        txt_data.value = date_picker.value.strftime("%d/%m/%Y")
        save_draft("data", txt_data.value)
        page.update()

    date_picker = ft.DatePicker(
        on_change=on_date_change,
        first_date=datetime.datetime(2023, 1, 1),
        last_date=datetime.datetime(2030, 12, 31),
    )
    page.overlay.append(date_picker)

    txt_data = ft.TextField(
        label="Data", 
        value=get_draft("data") or datetime.datetime.now().strftime("%d/%m/%Y"), 
        read_only=True,
        on_focus=lambda _: page.open(date_picker),
        icon=ft.Icons.CALENDAR_MONTH
    )

    # --- DROPDOWNS ---
    dd_lider = ft.Dropdown(label="Líder", expand=True, on_change=lambda e: save_draft("lider", e.control.value))
    dd_maquina = ft.Dropdown(label="Máquina", expand=True, on_change=lambda e: save_draft("maquina", e.control.value))
    dd_turma = ft.Dropdown(label="Turma", expand=True, on_change=lambda e: save_draft("turma", e.control.value))
    dd_rota = ft.Dropdown(label="Rota", expand=True, on_change=lambda e: save_draft("rota", e.control.value))

    # --- CÂMERA ---
    def on_file_result(e: ft.FilePickerResultEvent):
        if e.files:
            secao = page.session.get("current_section")
            user_data["fotos"][secao] = e.files[0].path
            page.snack_bar = ft.SnackBar(ft.Text(f"Foto salva para {secao}"))
            page.snack_bar.open = True
            page.update()

    file_picker = ft.FilePicker(on_result=on_file_result)
    page.overlay.append(file_picker)

    # --- PDF ---
    def gerar_pdf(e):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(200, 10, txt="RELATÓRIO DE ROTA FITESA", ln=True, align='C')
        pdf.set_font("Arial", size=12)
        pdf.ln(10)
        pdf.cell(200, 10, txt=f"Data: {txt_data.value} | Lider: {dd_lider.value}", ln=True)
        pdf.cell(200, 10, txt=f"Maq: {dd_maquina.value} | Turma: {dd_turma.value}", ln=True)
        
        data_fmt = txt_data.value.replace("/", "_")
        nome_arq = f"{data_fmt}_{dd_turma.value}_{dd_lider.value}.pdf"
        pdf.output(nome_arq)
        
        conn.cursor().execute("INSERT INTO historico (data, info) VALUES (?, ?)", (txt_data.value, nome_arq))
        conn.commit()
        
        page.snack_bar = ft.SnackBar(ft.Text(f"Gerado: {nome_arq}"))
        page.snack_bar.open = True
        page.update()

    # --- NAVEGAÇÃO ---
    def on_nav_change(e):
        index = e.control.selected_index
        if index == 0: show_menu()
        elif index == 1: show_rota()
        elif index == 2: check_admin_pass()

    page.navigation_bar = ft.NavigationBar(
        destinations=[
            ft.NavigationBarDestination(icon=ft.Icons.HOME, label="Início"),
            ft.NavigationBarDestination(icon=ft.Icons.ROUTE, label="Rota"),
            ft.NavigationBarDestination(icon=ft.Icons.SETTINGS, label="Admin"),
        ],
        on_change=on_nav_change,
        visible=False
    )

    # --- TELAS ---
    def show_login(e=None):
        page.clean()
        page.navigation_bar.visible = False
        user_input = ft.TextField(label="Usuário", value="admin")
        pass_input = ft.TextField(label="Senha", password=True, can_reveal_password=True, value="admin")
        
        def login_click(e):
            if user_input.value == "admin" and pass_input.value == "admin":
                page.navigation_bar.visible = True
                show_menu()
            else:
                page.snack_bar = ft.SnackBar(ft.Text("Login incorreto"))
                page.snack_bar.open = True
                page.update()

        page.add(
            ft.Column([
                ft.Container(height=50),
                ft.Text("Login Fitesa", size=30, weight="bold"),
                container_campo(user_input),
                container_campo(pass_input),
                ft.ElevatedButton("Entrar", on_click=login_click, width=200)
            ], horizontal_alignment="center")
        )

    def show_menu():
        nonlocal current_nav_index
        current_nav_index = 0
        page.clean()
        page.navigation_bar.selected_index = 0
        page.add(
            ft.AppBar(title=ft.Text("Início"), bgcolor=ft.Colors.BLUE_GREY_100, automatically_imply_leading=False),
            ft.Column([
                ft.Container(height=40),
                ft.Icon(ft.Icons.DIRECTIONS_RUN, size=80),
                container_campo(ft.ElevatedButton("Realizar Rota", icon=ft.Icons.PLAY_ARROW, on_click=lambda _: show_rota(), height=60)),
                container_campo(ft.ElevatedButton("Configurações", icon=ft.Icons.SETTINGS, on_click=lambda _: check_admin_pass(), height=60)),
            ], horizontal_alignment="center")
        )

    def show_rota(e=None):
        nonlocal current_nav_index
        current_nav_index = 1
        page.clean()
        page.navigation_bar.selected_index = 1
        
        cursor = conn.cursor()
        dd_lider.options = [ft.dropdown.Option(r[0]) for r in cursor.execute("SELECT nome FROM opcoes WHERE tipo='lider'").fetchall()]
        dd_maquina.options = [ft.dropdown.Option(r[0]) for r in cursor.execute("SELECT nome FROM opcoes WHERE tipo='maquina'").fetchall()]
        dd_turma.options = [ft.dropdown.Option(r[0]) for r in cursor.execute("SELECT nome FROM opcoes WHERE tipo='turma'").fetchall()]
        dd_rota.options = [ft.dropdown.Option(r[0]) for r in cursor.execute("SELECT nome FROM opcoes WHERE tipo='rota'").fetchall()]
        
        dd_lider.value = get_draft("lider")
        dd_maquina.value = get_draft("maquina")
        dd_turma.value = get_draft("turma")
        dd_rota.value = get_draft("rota")

        itens_ui = ft.Column()
        for r in cursor.execute("SELECT titulo FROM rotina_itens").fetchall():
            titulo = r[0]
            itens_ui.controls.append(
                container_campo(
                    ft.Column([
                        ft.Text(titulo, weight="bold"),
                        ft.ElevatedButton("Câmera", icon=ft.Icons.CAMERA_ALT, on_click=lambda e, t=titulo: (page.session.set("current_section", t), file_picker.pick_files(capture=True))),
                        ft.TextField(label="Observação", multiline=True, on_change=lambda e, t=titulo: save_draft(f"obs_{t}", e.control.value), value=get_draft(f"obs_{titulo}"))
                    ])
                )
            )

        page.add(
            ft.AppBar(title=ft.Text("Realizar Rota"), bgcolor=ft.Colors.BLUE_GREY_100, automatically_imply_leading=False),
            container_campo(ft.Text("1. Identificação", size=20, weight="bold")),
            container_campo(txt_data), container_campo(dd_lider), container_campo(dd_maquina), container_campo(dd_turma), container_campo(dd_rota),
            ft.Divider(),
            container_campo(ft.Text("2. Rotina", size=20, weight="bold")),
            itens_ui,
            container_campo(ft.ElevatedButton("Gerar PDF", on_click=gerar_pdf, bgcolor=ft.Colors.GREEN, color=ft.Colors.WHITE, height=50)),
            ft.Container(height=60)
        )

    def check_admin_pass(e=None):
        pw = ft.TextField(
            label="Senha Admin", 
            password=True, 
            can_reveal_password=True, 
            autofocus=True,
            on_submit=lambda _: validar(None)
        )
        
        def validar(e):
            if pw.value == "production26":
                dlg.open = False # FECHA O ESTADO DO DIÁLOGO
                page.update()    # FORÇA A REMOÇÃO VISUAL DO OVERLAY
                show_admin()     # CARREGA A TELA DE ADMINISTRAÇÃO
            else:
                pw.error_text = "Senha Incorreta"
                page.update()

        def cancelar(e):
            dlg.open = False
            page.navigation_bar.selected_index = current_nav_index
            page.update()

        dlg = ft.AlertDialog(
            title=ft.Text("Acesso Restrito"),
            content=ft.Column([
                ft.Text("Digite a senha de produção para gerenciar os itens."),
                pw
            ], tight=True),
            actions=[
                ft.TextButton("Entrar", on_click=validar),
                ft.TextButton("Cancelar", on_click=cancelar, icon=ft.Icons.CLOSE, icon_color="red")
            ],
            modal=True
        )
        page.open(dlg)

    def show_admin(e=None):
        nonlocal current_nav_index
        current_nav_index = 2
        page.clean()
        page.navigation_bar.selected_index = 2
        
        def deletar_item(tabela, item_id):
            cursor = conn.cursor()
            cursor.execute(f"DELETE FROM {tabela} WHERE id = ?", (item_id,))
            conn.commit()
            show_admin()

        def editar_item(tabela, item_id, valor_atual):
            edit_field = ft.TextField(value=valor_atual, autofocus=True)
            def salvar_edicao(e):
                cursor = conn.cursor()
                coluna = "titulo" if tabela == "rotina_itens" else "nome"
                cursor.execute(f"UPDATE {tabela} SET {coluna} = ? WHERE id = ?", (edit_field.value, item_id))
                conn.commit()
                page.close(dlg_edit)
                show_admin()
            dlg_edit = ft.AlertDialog(title=ft.Text("Editar Item"), content=edit_field, actions=[ft.TextButton("Salvar", on_click=salvar_edicao)])
            page.open(dlg_edit)

        novo_item_input = ft.TextField(label="Nome do Item", expand=True)
        tipo_item_dd = ft.Dropdown(label="Tipo", expand=True, options=[
            ft.dropdown.Option("lider", "Líder"), ft.dropdown.Option("maquina", "Máquina"),
            ft.dropdown.Option("turma", "Turma"), ft.dropdown.Option("rota", "Rota"),
            ft.dropdown.Option("rotina", "Item de Rotina")
        ])

        def cadastrar(e):
            if not novo_item_input.value or not tipo_item_dd.value: return
            if tipo_item_dd.value == "rotina":
                conn.cursor().execute("INSERT INTO rotina_itens (titulo) VALUES (?)", (novo_item_input.value,))
            else:
                # CORREÇÃO AQUI: Adicionado o segundo '?' para os dois valores
                conn.cursor().execute("INSERT INTO opcoes (tipo, nome) VALUES (?, ?)", (tipo_item_dd.value, novo_item_input.value))
            conn.commit()
            novo_item_input.value = ""
            show_admin()

        def gerar_lista_categoria(tipo):
            cursor = conn.cursor()
            col = ft.Column(scroll=ft.ScrollMode.ALWAYS, height=350, spacing=5)
            
            if tipo == "rotina":
                dados = cursor.execute("SELECT id, titulo FROM rotina_itens").fetchall()
                tabela = "rotina_itens"
            else:
                dados = cursor.execute("SELECT id, nome FROM opcoes WHERE tipo=?", (tipo,)).fetchall()
                tabela = "opcoes"

            for r in dados:
                col.controls.append(
                    ft.Container(
                        content=ft.Row([
                            ft.Text(r[1], expand=True),
                            ft.IconButton(ft.Icons.EDIT, icon_size=20, on_click=lambda e, i=r[0], v=r[1]: editar_item(tabela, i, v)),
                            ft.IconButton(ft.Icons.DELETE, icon_size=20, icon_color="red", on_click=lambda e, i=r[0]: deletar_item(tabela, i))
                        ]),
                        padding=5, border=ft.border.all(1, ft.Colors.BLACK12), border_radius=5
                    )
                )
            return col

        tabs_admin = ft.Tabs(
            selected_index=0,
            animation_duration=300,
            tabs=[
                ft.Tab(text="Líder", icon=ft.Icons.PERSON, content=gerar_lista_categoria("lider")),
                ft.Tab(text="Máquina", icon=ft.Icons.PRECISION_MANUFACTURING, content=gerar_lista_categoria("maquina")),
                ft.Tab(text="Turma", icon=ft.Icons.GROUP, content=gerar_lista_categoria("turma")),
                ft.Tab(text="Rota", icon=ft.Icons.MAP, content=gerar_lista_categoria("rota")),
                ft.Tab(text="Rotina", icon=ft.Icons.CHECKLIST, content=gerar_lista_categoria("rotina")),
            ],
            expand=1
        )

        page.add(
            ft.AppBar(title=ft.Text("Administração"), bgcolor=ft.Colors.RED_100, automatically_imply_leading=False),
            container_campo(ft.Text("Adicionar Novo", size=18, weight="bold")),
            container_campo(ft.Row([novo_item_input, tipo_item_dd])),
            container_campo(ft.ElevatedButton("Salvar Novo Item", on_click=cadastrar, width=page.width, icon=ft.Icons.ADD)),
            ft.Divider(),
            container_campo(ft.Text("Gerenciar Itens Existentes", size=18, weight="bold")),
            ft.Container(content=tabs_admin, padding=10, expand=True),
            ft.Container(height=60)
        )

    show_login()

ft.app(target=main)