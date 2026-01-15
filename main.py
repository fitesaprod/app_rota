import flet as ft
import sqlite3
import datetime
import os
import sys
import traceback

# --- CONFIGURAÇÃO INICIAL E SEGURANÇA ---
try:
    from fpdf import FPDF
    fpdf_disponivel = True
except ImportError as e:
    fpdf_disponivel = False
    erro_import = str(e)

def main(page: ft.Page):
    # --- 1. CONFIGURAÇÃO VISUAL PRELIMINAR (EVITA TELA BRANCA) ---
    page.title = "Fitesa Mobile"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 0
    page.scroll = "hidden"
    page.bgcolor = ft.Colors.GREY_50
    
    page.theme = ft.Theme(
        color_scheme_seed=ft.Colors.INDIGO,
        visual_density=ft.VisualDensity.COMFORTABLE,
        use_material3=True 
    )

    # Força uma atualização inicial para garantir que a tela carregue
    page.update()

    # --- 2. DEFINIÇÃO DE CAMINHOS SEGUROS (ANDROID/PC) ---
    # No Android, os.getcwd() é somente leitura. Usamos o HOME interno do app.
    try:
        rota_base = os.environ.get("HOME")
        if not rota_base:
            rota_base = os.getcwd() # Fallback para PC
            
        # Nome do banco de dados
        db_path = os.path.join(rota_base, "fitesa_rotas.db")
    except Exception as e:
        page.add(ft.Text(f"Erro Crítico de Caminho: {e}", color="red"))
        return

    # --- 3. INICIALIZAÇÃO DO BANCO DE DADOS (COM TRATAMENTO DE ERRO) ---
    conn = None
    cursor = None
    
    try:
        conn = sqlite3.connect(db_path, check_same_thread=False)
        cursor = conn.cursor()
        
        # Tabelas básicas
        cursor.execute("CREATE TABLE IF NOT EXISTS opcoes (id INTEGER PRIMARY KEY, tipo TEXT, nome TEXT)")
        cursor.execute("CREATE TABLE IF NOT EXISTS rotina_itens (id INTEGER PRIMARY KEY, titulo TEXT)")
        cursor.execute("CREATE TABLE IF NOT EXISTS historico (id INTEGER PRIMARY KEY, data TEXT, info TEXT)")
        cursor.execute("CREATE TABLE IF NOT EXISTS rascunho (id TEXT PRIMARY KEY, valor TEXT)")
        
        # Verificação de coluna 'ordem' (Migração)
        try:
            cursor.execute("SELECT ordem FROM rotina_itens LIMIT 1")
        except sqlite3.OperationalError:
            cursor.execute("ALTER TABLE rotina_itens ADD COLUMN ordem INTEGER DEFAULT 0")
            conn.commit()
            
        conn.commit()
        
    except Exception as e:
        # Se der erro no banco, mostra na tela em vez de travar (Tela Branca)
        err_msg = traceback.format_exc()
        page.clean()
        page.add(
            ft.Container(
                content=ft.Column([
                    ft.Icon(ft.Icons.ERROR, color="red", size=50),
                    ft.Text("Erro ao iniciar Banco de Dados:", weight="bold"),
                    ft.Text(str(e), color="red"),
                    ft.Text(f"Caminho tentado: {db_path}", size=12),
                    ft.ExpansionTile(
                        title=ft.Text("Detalhes Técnicos"),
                        controls=[ft.Text(err_msg, size=10, font_family="monospace")]
                    )
                ]),
                padding=20,
                alignment=ft.alignment.center
            )
        )
        page.update()
        return # Para a execução aqui se não tiver DB

    # --- COMPONENTES VISUAIS (WIDGETS PERSONALIZADOS) ---
    
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
            shadow=ft.BoxShadow(
                spread_radius=1,
                blur_radius=10,
                color=ft.Colors.BLUE_GREY_50,
                offset=ft.Offset(0, 4),
            ),
            margin=ft.margin.only(bottom=15, left=15, right=15)
        )

    # Variáveis globais de estado
    user_data = {"fotos": {}}
    current_nav_index = 0

    # --- FUNÇÕES DE LÓGICA ---
    def save_draft(key, value):
        try:
            if conn:
                local_cursor = conn.cursor()
                local_cursor.execute("INSERT OR REPLACE INTO rascunho (id, valor) VALUES (?, ?)", (key, str(value)))
                conn.commit()
        except: pass

    def get_draft(key):
        try:
            if conn:
                res = conn.cursor().execute("SELECT valor FROM rascunho WHERE id = ?", (key,)).fetchone()
                return res[0] if res else ""
            return ""
        except: return ""

    # --- SELETORES E CAMPOS ---
    def on_date_change(e):
        if date_picker.value:
            txt_data.value = date_picker.value.strftime("%d/%m/%Y")
            save_draft("data", txt_data.value)
            page.update()

    date_picker = ft.DatePicker(
        on_change=on_date_change,
        first_date=datetime.datetime(2023, 1, 1),
        last_date=datetime.datetime(2030, 12, 31),
    )
    # Importante: Adicionar overlay depois garante que a page existe
    page.overlay.append(date_picker)

    txt_data = ft.TextField(
        label="Data Selecionada",
        value=get_draft("data") or datetime.datetime.now().strftime("%d/%m/%Y"),
        read_only=True,
        on_focus=lambda _: date_picker.pick_date(),
        border_radius=10,
        prefix_icon=ft.Icons.CALENDAR_MONTH,
        text_size=16
    )

    dd_lider = ft.Dropdown(label="Selecione o Líder", border_radius=10, expand=True, on_change=lambda e: save_draft("lider", e.control.value))
    dd_maquina = ft.Dropdown(label="Selecione a Máquina", border_radius=10, expand=True, on_change=lambda e: save_draft("maquina", e.control.value))
    dd_turma = ft.Dropdown(label="Selecione a Turma", border_radius=10, expand=True, on_change=lambda e: save_draft("turma", e.control.value))
    dd_rota = ft.Dropdown(label="Selecione a Rota", border_radius=10, expand=True, on_change=lambda e: save_draft("rota", e.control.value))

    # --- CÂMERA ---
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
        try:
            if not fpdf_disponivel:
                raise Exception("Biblioteca FPDF não instalada ou não suportada.")
            
            pdf = FPDF()
            pdf.add_page()
            
            # Cabeçalho
            pdf.set_font("Arial", 'B', 16)
            pdf.cell(0, 10, txt="RELATORIO DE ROTA FITESA", ln=True, align='C')
            pdf.set_font("Arial", size=12)
            pdf.ln(5)
            
            pdf.cell(0, 10, txt=f"Data: {txt_data.value}", ln=True)
            pdf.cell(0, 10, txt=f"Lider: {dd_lider.value} | Turma: {dd_turma.value}", ln=True)
            pdf.cell(0, 10, txt=f"Maquina: {dd_maquina.value} | Rota: {dd_rota.value}", ln=True)
            pdf.ln(5)
            
            # Linha divisória
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            pdf.ln(5)
            
            # --- LOOP PARA PEGAR OS ITENS (COM ORDEM CORRETA) ---
            local_cursor = conn.cursor()
            itens = local_cursor.execute("SELECT titulo FROM rotina_itens ORDER BY ordem ASC, id ASC").fetchall()
            
            if not itens:
                pdf.cell(0, 10, txt="Nenhum item de verificação cadastrado.", ln=True)
            else:
                for item in itens:
                    titulo = item[0]
                    obs = get_draft(f"obs_{titulo}")
                    
                    pdf.set_font("Arial", 'B', 12)
                    pdf.cell(0, 8, txt=f"- {titulo}", ln=True)
                    
                    if obs:
                        pdf.set_font("Arial", size=11)
                        pdf.multi_cell(0, 6, txt=f"  Obs: {obs}")
                    else:
                        pdf.set_font("Arial", 'I', 10)
                        pdf.cell(0, 6, txt="  (Sem observacoes)", ln=True)
                    
                    pdf.ln(2)

            # Salvar Arquivo
            data_fmt = txt_data.value.replace("/", "_")
            turma_fmt = str(dd_turma.value).replace(" ", "_") if dd_turma.value else "GERAL"
            nome_arq = f"{data_fmt}_{turma_fmt}.pdf"
            
            # Caminho completo seguro
            caminho_pdf = os.path.join(rota_base, nome_arq)
            
            pdf.output(caminho_pdf)
            
            local_cursor.execute("INSERT INTO historico (data, info) VALUES (?, ?)", (txt_data.value, nome_arq))
            conn.commit()
            
            page.snack_bar = ft.SnackBar(ft.Text(f"PDF salvo em: {caminho_pdf}"), bgcolor="green")
            page.open(page.snack_bar)
            page.update()
            
        except Exception as ex:
            msg_erro = str(ex)
            # Tratamento especial para erro de permissão
            if "Permission denied" in msg_erro:
                msg_erro = "Sem permissão de escrita. Verifique as configurações do Android."
                
            page.snack_bar = ft.SnackBar(ft.Text(f"Erro ao gerar PDF: {msg_erro}"), bgcolor="red")
            page.open(page.snack_bar)
            page.update()

    # --- NAVEGAÇÃO ---
    def on_nav_change(e):
        index = e.control.selected_index
        if index == 0: show_menu()
        elif index == 1: show_rota()
        elif index == 2: check_admin_pass()

    page.navigation_bar = ft.NavigationBar(
        selected_index=0,
        destinations=[
            ft.NavigationBarDestination(icon=ft.Icons.HOME_OUTLINED, selected_icon=ft.Icons.HOME, label="Início"),
            ft.NavigationBarDestination(icon=ft.Icons.ASSIGNMENT_OUTLINED, selected_icon=ft.Icons.ASSIGNMENT, label="Rota"),
            ft.NavigationBarDestination(icon=ft.Icons.ADMIN_PANEL_SETTINGS_OUTLINED, selected_icon=ft.Icons.ADMIN_PANEL_SETTINGS, label="Admin"),
        ],
        on_change=on_nav_change,
        bgcolor="white",
        elevation=10,
        visible=False
    )

    # --- TELAS ---
    def show_login(e=None):
        page.clean()
        page.navigation_bar.visible = False
        user_input = ft.TextField(label="Usuário", border_radius=10, prefix_icon=ft.Icons.PERSON)
        pass_input = ft.TextField(label="Senha", password=True, can_reveal_password=True, border_radius=10, prefix_icon=ft.Icons.LOCK)
        
        def login_click(e):
            # Login simples para exemplo
            if (user_input.value == "admin" and pass_input.value == "admin") or (user_input.value == "lider" and pass_input.value == "123"):
                page.navigation_bar.visible = True
                show_menu()
            else:
                page.snack_bar = ft.SnackBar(ft.Text("Dados incorretos"), bgcolor="red")
                page.open(page.snack_bar)
                page.update()

        page.add(
            ft.Container(
                content=ft.Column([
                    ft.Icon(ft.Icons.FACTORY, size=80, color=ft.Colors.PRIMARY),
                    ft.Text("Fitesa", size=30, weight="bold", color=ft.Colors.PRIMARY),
                    ft.Text("Gestão de Produção", size=16, color="grey"),
                    ft.Divider(height=40, color="transparent"),
                    user_input,
                    ft.Divider(height=10, color="transparent"),
                    pass_input,
                    ft.Divider(height=30, color="transparent"),
                    ft.ElevatedButton(
                        "ACESSAR SISTEMA", 
                        on_click=login_click, 
                        width=300, 
                        height=50,
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=10),
                            bgcolor=ft.Colors.PRIMARY,
                            color="white"
                        )
                    )
                ], horizontal_alignment="center"),
                alignment=ft.alignment.center,
                expand=True,
                padding=40
            )
        )
        page.update()

    def show_menu():
        nonlocal current_nav_index
        current_nav_index = 0
        page.clean()
        page.navigation_bar.selected_index = 0
        
        header = ft.Container(
            content=ft.Column([
                ft.Text("Olá, Lider", size=28, weight="bold", color="white"),
                ft.Text("Tenha uma ótima rota!", size=14, color="white70")
            ]),
            bgcolor=ft.Colors.PRIMARY,
            padding=ft.padding.only(left=20, right=20, top=60, bottom=30),
            border_radius=ft.border_radius.only(bottom_left=30, bottom_right=30),
            shadow=ft.BoxShadow(blur_radius=15, color=ft.Colors.BLUE_GREY_200)
        )

        btn_rota = ft.Container(
            content=ft.Column([
                ft.Icon(ft.Icons.PLAY_CIRCLE_FILL, size=50, color=ft.Colors.PRIMARY),
                ft.Text("Iniciar Nova Rota", weight="bold", size=16),
                ft.Text("Apontamento diário", size=12, color="grey")
            ], alignment="center", horizontal_alignment="center"),
            bgcolor="white", padding=20, border_radius=20,
            shadow=ft.BoxShadow(blur_radius=10, color=ft.Colors.GREY_200),
            on_click=lambda _: show_rota(),
            expand=True
        )

        btn_config = ft.Container(
            content=ft.Column([
                ft.Icon(ft.Icons.SETTINGS, size=50, color=ft.Colors.ORANGE),
                ft.Text("Configurações", weight="bold", size=16),
                ft.Text("Gerenciar Itens", size=12, color="grey")
            ], alignment="center", horizontal_alignment="center"),
            bgcolor="white", padding=20, border_radius=20,
            shadow=ft.BoxShadow(blur_radius=10, color=ft.Colors.GREY_200),
            on_click=lambda _: check_admin_pass(),
            expand=True
        )

        page.add(
            ft.Column([
                header,
                ft.Container(
                    content=ft.Row([btn_rota, btn_config], spacing=20),
                    padding=20,
                    margin=ft.margin.only(top=-20) 
                )
            ])
        )
        page.update()

    def show_rota(e=None):
        nonlocal current_nav_index
        current_nav_index = 1
        page.clean()
        page.navigation_bar.selected_index = 1
        
        try:
            local_cursor = conn.cursor()
            dd_lider.options = [ft.dropdown.Option(r[0]) for r in local_cursor.execute("SELECT nome FROM opcoes WHERE tipo='lider'").fetchall()]
            dd_maquina.options = [ft.dropdown.Option(r[0]) for r in local_cursor.execute("SELECT nome FROM opcoes WHERE tipo='maquina'").fetchall()]
            dd_turma.options = [ft.dropdown.Option(r[0]) for r in local_cursor.execute("SELECT nome FROM opcoes WHERE tipo='turma'").fetchall()]
            dd_rota.options = [ft.dropdown.Option(r[0]) for r in local_cursor.execute("SELECT nome FROM opcoes WHERE tipo='rota'").fetchall()]
            
            dd_lider.value = get_draft("lider")
            dd_maquina.value = get_draft("maquina")
            dd_turma.value = get_draft("turma")
            dd_rota.value = get_draft("rota")

            # Lista agora usa a ORDEM salva no banco
            lista_itens = ft.Column(spacing=15)
            for r in local_cursor.execute("SELECT titulo FROM rotina_itens ORDER BY ordem ASC, id ASC").fetchall():
                titulo = r[0]
                lista_itens.controls.append(
                    ft.Container(
                        content=ft.Column([
                            ft.Row([
                                ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE, color="grey"),
                                ft.Text(titulo, weight="w500", size=15),
                            ]),
                            ft.Row([
                                ft.IconButton(ft.Icons.CAMERA_ALT, icon_color=ft.Colors.PRIMARY, on_click=lambda e, t=titulo: (page.session.set("current_section", t), file_picker.pick_files(capture=True))),
                                ft.TextField(hint_text="Observação...", text_size=13, expand=True, border_radius=8, content_padding=10, on_change=lambda e, t=titulo: save_draft(f"obs_{t}", e.control.value), value=get_draft(f"obs_{titulo}"))
                            ])
                        ]),
                        bgcolor="white", padding=15, border_radius=10, border=ft.border.all(1, ft.Colors.GREY_200)
                    )
                )

        except Exception as e:
            page.add(ft.Text(f"Erro ao carregar rota: {e}", color="red"))
            return

        def limpar_campos(e):
            conn.cursor().execute("DELETE FROM rascunho")
            conn.commit()
            page.snack_bar = ft.SnackBar(ft.Text("Todos os campos foram limpos!"))
            page.open(page.snack_bar)
            show_rota()

        page.add(
            ft.Container(
                content=ft.Row([
                    ft.Text("Nova Rota", size=20, weight="bold"),
                    ft.Icon(ft.Icons.ASSIGNMENT, color=ft.Colors.PRIMARY)
                ], alignment="spaceBetween"),
                padding=ft.padding.only(left=20, right=20, top=40, bottom=10),
                bgcolor="white"
            ),
            ft.Column([
                criar_card("1. Identificação", ft.Column([
                    txt_data, dd_lider, dd_maquina, dd_turma, dd_rota
                ]), icone=ft.Icons.PERSON_SEARCH),
                
                ft.Container(
                    content=ft.Text("2. Checklist de Rotina", weight="bold", size=16, color=ft.Colors.PRIMARY),
                    padding=ft.padding.only(left=25, bottom=5)
                ),
                
                ft.Container(content=lista_itens, padding=ft.padding.only(left=15, right=15)),
                
                ft.Container(height=20),
                
                ft.Container(
                    content=ft.Column([
                        ft.ElevatedButton(
                            "Limpar Campos",
                            icon=ft.Icons.CLEANING_SERVICES,
                            on_click=limpar_campos,
                            style=ft.ButtonStyle(
                                bgcolor=ft.Colors.RED_400,
                                color="white",
                                shape=ft.RoundedRectangleBorder(radius=10),
                                padding=15
                            ),
                            width=page.width
                        ),
                        ft.Container(height=10),
                        ft.ElevatedButton(
                            "Finalizar e Gerar PDF", 
                            icon=ft.Icons.PICTURE_AS_PDF,
                            on_click=gerar_pdf,
                            style=ft.ButtonStyle(
                                bgcolor=ft.Colors.GREEN,
                                color="white",
                                shape=ft.RoundedRectangleBorder(radius=10),
                                padding=20
                            ),
                            width=page.width
                        )
                    ]),
                    padding=20
                ),
                ft.Container(height=80) 
            ], scroll="auto", expand=True)
        )
        page.update()

    def check_admin_pass(e=None):
        pw = ft.TextField(label="Senha", password=True, text_align="center", border_radius=10)
        def validar(e):
            # Senha de exemplo
            if pw.value == "production26":
                dlg.open = False
                page.update()
                show_admin()
            else:
                pw.error_text = "Senha Incorreta"
                page.update()

        dlg = ft.AlertDialog(
            title=ft.Text("Acesso Restrito"),
            content=ft.Container(content=pw, height=70),
            actions=[ft.TextButton("Entrar", on_click=validar)],
            actions_alignment="center",
            shape=ft.RoundedRectangleBorder(radius=15)
        )
        page.open(dlg)

    def show_admin(e=None):
        nonlocal current_nav_index
        current_nav_index = 2
        page.clean()
        page.navigation_bar.selected_index = 2
        
        novo_item_input = ft.TextField(label="Novo Item...", expand=True, border_radius=10)
        tipo_item_dd = ft.Dropdown(label="Categoria", width=120, border_radius=10, options=[
            ft.dropdown.Option("lider", "Líder"), ft.dropdown.Option("maquina", "Máq."),
            ft.dropdown.Option("turma", "Turma"), ft.dropdown.Option("rota", "Rota"),
            ft.dropdown.Option("rotina", "Checklist (Arrastável)")
        ])

        def cadastrar(e):
            if not novo_item_input.value or not tipo_item_dd.value: return
            
            local_cursor = conn.cursor()
            if tipo_item_dd.value == "rotina":
                res = local_cursor.execute("SELECT MAX(ordem) FROM rotina_itens").fetchone()
                nova_ordem = (res[0] if res and res[0] is not None else 0) + 1
                local_cursor.execute("INSERT INTO rotina_itens (titulo, ordem) VALUES (?, ?)", (novo_item_input.value, nova_ordem))
            else:
                local_cursor.execute("INSERT INTO opcoes (tipo, nome) VALUES (?, ?)", (tipo_item_dd.value, novo_item_input.value))
            conn.commit()
            novo_item_input.value = ""
            page.snack_bar = ft.SnackBar(ft.Text("Item adicionado!"), bgcolor="green")
            page.open(page.snack_bar)
            show_admin()

        def deletar(tabela, id_item):
            conn.cursor().execute(f"DELETE FROM {tabela} WHERE id=?", (id_item,))
            conn.commit()
            show_admin()

        # --- LÓGICA DE DRAG & DROP ---
        def drag_accept(e):
            try:
                src_id = int(e.data)
                tgt_id = int(e.control.data)
            except: return
                
            if src_id == tgt_id: return

            local_cursor = conn.cursor()
            rows = local_cursor.execute("SELECT id FROM rotina_itens ORDER BY ordem ASC, id ASC").fetchall()
            ids_atuais = [r[0] for r in rows]
            
            if src_id in ids_atuais and tgt_id in ids_atuais:
                src_index = ids_atuais.index(src_id)
                tgt_index = ids_atuais.index(tgt_id)
                ids_atuais.remove(src_id)
                
                # Ajuste de inserção
                insert_index = ids_atuais.index(tgt_id)
                if src_index < tgt_index:
                    ids_atuais.insert(insert_index + 1, src_id)
                else:
                    ids_atuais.insert(insert_index, src_id)
                
                for idx, item_id in enumerate(ids_atuais):
                    local_cursor.execute("UPDATE rotina_itens SET ordem = ? WHERE id = ?", (idx, item_id))
                conn.commit()
                show_admin()

        def lista_simples(tipo):
            if tipo == "rotina":
                items_col = ft.Column(spacing=5)
                dados = conn.cursor().execute("SELECT id, titulo FROM rotina_itens ORDER BY ordem ASC, id ASC").fetchall()
                
                for r in dados:
                    item_id = r[0]
                    texto = r[1]
                    
                    card_content = ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.Icons.DRAG_INDICATOR, color="grey", size=20),
                            ft.Text(texto, expand=True, size=14),
                            ft.IconButton(ft.Icons.DELETE, icon_color="red", icon_size=18, on_click=lambda e, i=item_id: deletar("rotina_itens", i))
                        ]),
                        bgcolor="white", padding=10, border_radius=8, border=ft.border.all(1, ft.Colors.GREY_100),
                        width=page.width 
                    )

                    draggable = ft.Draggable(
                        group="rotina_group",
                        content=card_content,
                        content_when_dragging=ft.Container(content=card_content, opacity=0.5),
                        data=item_id,
                    )
                    
                    target = ft.DragTarget(
                        group="rotina_group",
                        content=draggable,
                        on_accept=drag_accept,
                        data=item_id,
                    )
                    
                    items_col.controls.append(target)
                return items_col

            else:
                tabela = "opcoes"
                sql = f"SELECT id, nome FROM {tabela} WHERE tipo='{tipo}'"
                items = ft.Column(spacing=5)
                for r in conn.cursor().execute(sql).fetchall():
                    items.controls.append(
                        ft.Container(
                            content=ft.Row([
                                ft.Text(r[1], expand=True, size=14),
                                ft.IconButton(ft.Icons.DELETE, icon_color="red", icon_size=18, on_click=lambda e, i=r[0]: deletar(tabela, i))
                            ]),
                            bgcolor="white", padding=10, border_radius=8, border=ft.border.all(1, ft.Colors.GREY_100)
                        )
                    )
                return items

        tabs = ft.Tabs(
            selected_index=0,
            animation_duration=300,
            indicator_color=ft.Colors.PRIMARY,
            label_color=ft.Colors.PRIMARY,
            unselected_label_color="grey",
            tabs=[
                ft.Tab(text="Líder", content=lista_simples("lider")),
                ft.Tab(text="Máq.", content=lista_simples("maquina")),
                ft.Tab(text="Turma", content=lista_simples("turma")),
                ft.Tab(text="Rota", content=lista_simples("rota")),
                ft.Tab(text="Rotina", content=lista_simples("rotina")),
            ],
            expand=True
        )

        page.add(
            ft.Container(
                content=ft.Text("Administração", size=20, weight="bold", color="white"),
                bgcolor=ft.Colors.PRIMARY,
                padding=ft.padding.only(left=20, right=20, top=50, bottom=20),
                width=page.width
            ),
            ft.Container(
                content=ft.Column([
                    ft.Row([novo_item_input, tipo_item_dd]),
                    ft.ElevatedButton("Adicionar", on_click=cadastrar, width=page.width, style=ft.ButtonStyle(bgcolor=ft.Colors.PRIMARY, color="white", shape=ft.RoundedRectangleBorder(radius=10))),
                    ft.Divider(),
                    tabs
                ]),
                padding=20,
                expand=True
            )
        )
        page.update()

    # Inicia no Login e força o update
    show_login()
    page.update()

ft.app(target=main)
