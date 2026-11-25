from __future__ import annotations
import queue
import threading
import time
from pathlib import Path
from tkinter import Tk, Canvas, StringVar, IntVar, Toplevel, Menu, filedialog, messagebox
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText
from . import __version__
from .jobs import Job
from .engine import QueueEngine
from .sessions import SessionPool
from .diagnostics import Diagnostics, picker_directory, remember_directory, sanitize

BG, WHITE, TEXT, MUTED = '#F5F6F8', '#FFFFFF', '#20242B', '#737983'
YELLOW, GREEN, RED, TINT, GRAPHITE = '#FFCC00', '#25834C', '#C62828', '#FFF2BD', '#343941'

class Tooltip:
    def __init__(self, widget, text):
        self.widget, self.text, self.window, self.after_id = widget, text, None, None
        widget.bind('<Enter>', self.enter)
        widget.bind('<Leave>', self.leave)
        widget.bind('<Destroy>', self.leave)
    def enter(self, _event=None):
        self.after_id = self.widget.after(450, self.show)
    def show(self):
        self.after_id = None
        self.window = Toplevel(self.widget)
        self.window.overrideredirect(True)
        self.window.geometry(f'+{self.widget.winfo_rootx()}+{self.widget.winfo_rooty()+self.widget.winfo_height()+3}')
        ttk.Label(self.window, text=self.text, padding=6).pack()
    def leave(self, _event=None):
        if self.after_id:
            self.widget.after_cancel(self.after_id)
            self.after_id = None
        if self.window:
            self.window.destroy()
            self.window = None

class UploaderApp(Tk):
    def __init__(self):
        super().__init__()
        self.title(f'PD Uploader  |  v{__version__}')
        self.geometry('1080x610')
        self.minsize(850, 520)
        self.configure(background=BG)
        self.events = queue.Queue()
        self.tasks = queue.Queue()
        self.pool = SessionPool()
        self.diagnostics = Diagnostics()
        self.engine = QueueEngine(self.pool.factory, lambda s: self.events.put(('state', s)), self._log)
        self.view_id = None
        self.state = self.engine.snapshot()
        self.state_at = time.monotonic()
        self.task_busy = False
        self.closing = False
        self.close_pending = False
        self.exit_was_running = False
        self.details_visible = False
        self.activity = []
        self.table_job_id = None
        self.table_views = {}
        self.tab_signature = None
        self.worker = threading.Thread(target=self._worker_loop, daemon=True)
        self._style()
        self._build()
        self.worker.start()
        self.after(80, self._poll)
        self.protocol('WM_DELETE_WINDOW', self._on_close)
        self.bind('<Control-o>', lambda e: self._add_files())
        import sys
        if sys.platform == 'darwin':
            self.bind('<Command-o>', lambda e: self._add_files())
        self._render()

    def _style(self):
        s = ttk.Style(self)
        s.theme_use('clam')
        s.configure('.', font=('Segoe UI', 10), foreground=TEXT, background=WHITE)
        s.configure('App.TFrame', background=BG)
        s.configure('Panel.TFrame', background=WHITE, bordercolor='#DADCE0', lightcolor='#DADCE0', darkcolor='#DADCE0', relief='solid', borderwidth=1)
        s.configure('TCheckbutton', background=WHITE, padding=0)
        s.map('TCheckbutton', background=[('active',WHITE),('disabled',WHITE)])
        s.configure('TScrollbar', background='#DADDE2', troughcolor=WHITE, bordercolor=WHITE, lightcolor=WHITE, darkcolor=WHITE, arrowsize=10)
        s.configure('Muted.TLabel', foreground=MUTED, font=('Segoe UI', 9))
        s.configure('Title.TLabel', font=('Segoe UI', 10, 'bold'))
        s.configure('Time.TLabel', font=('Segoe UI', 27, 'bold'))
        s.configure('TButton', padding=(10, 7), borderwidth=0, background=WHITE)
        s.map('TButton', background=[('active', '#ECEEF0')], foreground=[('disabled', '#969BA4')])
        s.configure('Primary.TButton', background=YELLOW, font=('Segoe UI', 10, 'bold'), padding=(8, 11))
        s.map('Primary.TButton', background=[('disabled', '#EEE8CB'), ('active', '#EDBD00')])
        s.configure('Running.TButton', background=GRAPHITE, foreground=WHITE, font=('Segoe UI', 10, 'bold'), padding=(8, 11))
        s.map('Running.TButton', background=[('active', '#20242B')], foreground=[('disabled', MUTED)])
        s.configure('Secondary.TButton', foreground=MUTED, font=('Segoe UI', 9), padding=(5, 4))
        s.configure('Treeview', rowheight=34, background=WHITE, fieldbackground=WHITE, borderwidth=0, font=('Segoe UI', 10))
        s.configure('Treeview.Heading', background='#FAFBFC', foreground=MUTED, padding=(8, 9), font=('Segoe UI', 9))
        s.map('Treeview', background=[('selected', '#F0F2F5')], foreground=[('selected', TEXT)])

    def _build(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        workspace = ttk.Frame(self, style='App.TFrame', padding=12)
        workspace.grid(row=0, column=0, sticky='nsew')
        workspace.columnconfigure(1, weight=1)
        workspace.rowconfigure(0, weight=1)
        monitor = ttk.Frame(workspace, style='Panel.TFrame', width=250)
        monitor.grid(row=0, column=0, sticky='ns', padx=(0, 12))
        monitor.grid_propagate(False)
        monitor.columnconfigure(0, weight=1)
        monitor.rowconfigure(7, weight=1)
        self.ring = Canvas(monitor, width=156, height=156, bg=WHITE, highlightthickness=0)
        self.ring.grid(row=0, column=0, pady=(24, 4))
        self.count_text = StringVar(value='0 / 0 images')
        ttk.Label(monitor, textvariable=self.count_text, style='Muted.TLabel').grid(row=1, column=0)
        self.timer_text = StringVar(value='00:00')
        ttk.Label(monitor, textvariable=self.timer_text, style='Time.TLabel').grid(row=2, column=0, pady=(20, 0))
        ttk.Label(monitor, text='Elapsed time', style='Muted.TLabel').grid(row=3, column=0)
        self.board_text = StringVar()
        ttk.Label(monitor, textvariable=self.board_text, style='Muted.TLabel').grid(row=4, column=0, pady=8)
        self.exceptions_text = StringVar()
        ttk.Label(monitor, textvariable=self.exceptions_text, wraplength=215, justify='center', style='Muted.TLabel').grid(row=5, column=0, padx=10)
        self.context_text = StringVar()
        ttk.Label(monitor, textvariable=self.context_text, wraplength=215, justify='center', style='Muted.TLabel').grid(row=8, column=0, padx=12, pady=(2, 6))
        self.main_button = ttk.Button(monitor, text='Open PD Board', style='Primary.TButton', command=self._main)
        self.main_button.grid(row=9, column=0, sticky='ew', padx=17)
        self.secondary = ttk.Frame(monitor, height=83)
        self.secondary.grid(row=10, column=0, sticky='ew', padx=12, pady=(4, 10))
        self.secondary.pack_propagate(False)

        right = ttk.Frame(workspace, style='Panel.TFrame')
        right.grid(row=0, column=1, sticky='nsew')
        right.columnconfigure(0, weight=1)
        right.rowconfigure(2, weight=1)
        self.tabs_canvas = Canvas(right, height=46, bg=WHITE, highlightthickness=0)
        self.tabs_canvas.grid(row=0, column=0, sticky='ew', padx=8, pady=(8, 0))
        self.tabs = ttk.Frame(self.tabs_canvas)
        self.tabs_window = self.tabs_canvas.create_window(0, 0, anchor='nw', window=self.tabs)
        self.tabs.bind('<Configure>', self._tabs_changed)
        self.tabs_canvas.bind('<Configure>', self._tabs_changed)
        self.tab_scroll = ttk.Scrollbar(right, orient='horizontal', command=self.tabs_canvas.xview)
        self.tab_scroll.grid(row=1, column=0, sticky='ew', padx=8)
        self.tabs_canvas.configure(xscrollcommand=self.tab_scroll.set)
        table_area = ttk.Frame(right)
        table_area.grid(row=2, column=0, sticky='nsew', padx=8, pady=(8, 10))
        table_area.columnconfigure(0, weight=1)
        table_area.rowconfigure(1, weight=1)
        table_header = self.table_header = ttk.Frame(table_area)
        table_header.grid(row=0, column=0, sticky='ew', columnspan=2, pady=(0, 8))
        table_header.columnconfigure(1, weight=1)
        self.all_var = IntVar()
        self.select_all = ttk.Checkbutton(table_header, text='Upload queue', variable=self.all_var, command=self._select_all)
        self.select_all.grid(row=0, column=0, sticky='w')
        self.job_count_text = StringVar()
        ttk.Label(table_header, textvariable=self.job_count_text, style='Muted.TLabel').grid(row=0, column=1, sticky='e')
        columns = ('use', 'row', 'tier', 'department', 'shift', 'metric', 'images', 'status')
        self.tree = ttk.Treeview(table_area, columns=columns, show='headings', selectmode='browse')
        widths = (42, 45, 85, 115, 80, 120, 60, 125)
        for name, width in zip(columns, widths):
            self.tree.heading(name, text={'use': 'Use', 'row': 'Row'}.get(name, name.title()))
            self.tree.column(name, width=width, minwidth=width, stretch=name in {'department', 'metric', 'status'}, anchor='center' if name in {'use','row','images'} else 'w')
        self.tree.grid(row=1, column=0, sticky='nsew')
        vertical = self.vertical = ttk.Scrollbar(table_area, orient='vertical', command=self.tree.yview)
        vertical.grid(row=1, column=1, sticky='ns')
        horizontal = self.horizontal = ttk.Scrollbar(table_area, orient='horizontal', command=self.tree.xview)
        horizontal.grid(row=2, column=0, sticky='ew')
        self.tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.tree.tag_configure('Uploaded', foreground=GREEN)
        self.tree.tag_configure('Failed', foreground=RED)
        self.tree.tag_configure('Outcome unknown', foreground=RED)
        self.tree.tag_configure('Uploading', background=TINT)
        for status in ('Waiting', 'Excluded', 'Skipped', 'Cancelled'):
            self.tree.tag_configure(status, foreground=MUTED)
        self.tree.bind('<Button-1>', self._tree_click)
        self.tree.bind('<space>', self._tree_space)
        self.tree.bind('<Double-1>', self._inspect_row)
        self.tree.bind('<Button-3>', self._row_menu)
        self.tree.bind('<<TreeviewSelect>>', self._row_hint)
        self.empty_label = ttk.Label(table_area, text='No CSV file loaded', style='Muted.TLabel', anchor='center')
        self.empty_label.grid(row=1, column=0, sticky='nsew')

        footer = ttk.Frame(self, style='App.TFrame', padding=(12, 3, 12, 6))
        footer.grid(row=1, column=0, sticky='ew')
        footer.columnconfigure(1, weight=1)
        self.log_toggle = ttk.Button(footer, text='› Activity log', style='Secondary.TButton', command=self._toggle_log)
        self.log_toggle.grid(row=0, column=0)
        self.footer_text = StringVar(value='Ready')
        ttk.Label(footer, textvariable=self.footer_text, background=BG, foreground=MUTED, wraplength=730).grid(row=0, column=1, sticky='e')
        self.log_frame = ttk.Frame(self, padding=(12, 0, 12, 12), style='App.TFrame')
        self.log_frame.columnconfigure(0, weight=1)
        buttons = ttk.Frame(self.log_frame, style='App.TFrame')
        buttons.grid(row=0, column=0, sticky='e')
        ttk.Button(buttons, text='Copy', style='Secondary.TButton', command=self._copy_log).pack(side='left')
        ttk.Button(buttons, text='Export', style='Secondary.TButton', command=self._export_log).pack(side='left')
        self.log_text = ScrolledText(self.log_frame, height=7, wrap='word', font=('Consolas', 9), relief='flat', state='disabled')
        self.log_text.grid(row=1, column=0, sticky='ew')

    def _worker_loop(self):
        while True:
            action = self.tasks.get()
            if action is None:
                try:
                    self.engine.close_sessions()
                    self.pool.close()
                finally:
                    self.events.put(('closed', None))
                return
            try:
                action()
            except Exception as exc:
                self._log(f'{type(exc).__name__}: {exc}')
                self.events.put(('error', sanitize(str(exc))))
            finally:
                self.events.put(('task_done', None))

    def _submit(self, action):
        if self.task_busy or self.closing:
            return
        self.task_busy = True
        self.tasks.put(action)
        self._render()

    def _log(self, message):
        text = self.diagnostics.write(message)
        self.events.put(('log', time.strftime('%H:%M:%S') + ' | ' + text))

    def _poll(self):
        redraw = False
        while True:
            try:
                kind, data = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == 'closed':
                self.diagnostics.close()
                self.destroy()
                return
            if kind == 'task_done':
                self.task_busy = False
                redraw = True
            elif kind == 'state':
                self.state, self.state_at = data, time.monotonic()
                try:
                    self.diagnostics.checkpoint(data)
                except OSError:
                    self.footer_text.set('Result journal could not be saved. Keep this window open to retain results.')
                redraw = True
            elif kind == 'error':
                messagebox.showerror('PD Uploader', data)
            elif kind == 'log':
                self.activity.append(data)
                self.activity = self.activity[-2000:]
                self.log_text.configure(state='normal')
                self.log_text.insert('end', data + '\n')
                if len(self.activity) == 2000:
                    self.log_text.delete('1.0', '2.0')
                self.log_text.see('end')
                self.log_text.configure(state='disabled')
        if redraw:
            self._render()
        self._timer()
        if self.close_pending and self.state['phase'] not in {'running', 'pausing'}:
            self.close_pending = False
            self._confirm_exit()
        self.after(100, self._poll)

    def _view(self):
        return next((j for j in self.state['jobs'] if j.id == self.view_id), None)

    def _render(self):
        state, jobs = self.state, self.state['jobs']
        if self.view_id not in {j.id for j in jobs}:
            self.view_id = jobs[0].id if jobs else None
        locked = state['started'] or state['phase'] == 'preparing' or self.task_busy
        self._render_tabs(jobs, state, locked)
        self._table()
        done, total = state['done'], state['total']
        self.count_text.set(f'{done} / {total} images')
        success = state['phase'] == 'finished' and total > 0 and done == total
        self.ring.delete('all')
        self.ring.create_oval(9, 9, 147, 147, outline='#E3E5E8', width=8)
        if state['percent']:
            if success:
                self.ring.create_oval(9, 9, 147, 147, outline=GREEN, width=8)
            else:
                self.ring.create_arc(9, 9, 147, 147, start=90, extent=-state['percent']*3.6, outline=YELLOW, width=8, style='arc')
        self.ring.create_text(78, 78, text='✓' if success else f"{state['percent']}%", font=('Segoe UI', 29, 'bold'), fill=GREEN if success else TEXT)
        required = [j for j in jobs if j.selected_count]
        if len(required) > 1 and state['phase'] in {'finished','cancelled'}:
            self.board_text.set('Queue finished' if state['phase']=='finished' else 'Queue cancelled')
        elif len(required) > 1:
            position = next((i+1 for i,j in enumerate(required) if j.id == state['current_id']), None)
            self.board_text.set(f'Board {position} of {len(required)}' if position else f'{sum(j.prepared for j in required)} / {len(required)} boards ready')
        else:
            self.board_text.set('')
        self.exceptions_text.set(' · '.join(f"{state['counts'].get(k, 0)} {k.lower()}" for k in ('Failed','Skipped','Cancelled','Outcome unknown') if state['counts'].get(k)))
        phase = state['phase']
        self.context_text.set(next((j.path.name for j in jobs if j.id == state['current_id']), '') if phase in {'preparing','reauth'} else '')
        label = {'empty':'Open PD Board', 'idle':'Open PD Board', 'ready':'Start all uploads' if len(required)>1 else 'Start upload',
                 'preparing':'Waiting for login', 'running':'Pause upload', 'pausing':'Pausing…', 'paused':'Resume upload',
                 'reauth':'Open PD Board', 'blocked':'Review upload result',
                 'finished':'Retry failed' if state['can_retry'] else 'New upload', 'cancelled':'New upload'}[phase]
        self.main_button.configure(text=label, style='Running.TButton' if phase=='running' else 'Primary.TButton')
        enabled = bool(total) and phase not in {'preparing','pausing'} and not self.closing
        if self.task_busy and phase not in {'running','paused','reauth','blocked'}:
            enabled = False
        if phase in {'finished','cancelled'}:
            enabled = not self.task_busy
        self.main_button.state(['!disabled' if enabled else 'disabled'])
        for child in self.secondary.winfo_children():
            child.destroy()
        def secondary(text, action):
            ttk.Button(self.secondary, text=text, command=action, style='Secondary.TButton').pack()
        if phase == 'preparing':
            secondary('Back', self.engine.back)
        if phase in {'paused','blocked','reauth'}:
            if state['current_id']:
                secondary('Skip current board', self._skip)
            secondary('Cancel all uploads', self._cancel)
        elif phase == 'finished' and state['can_retry']:
            secondary('New upload', self._new)
        self.footer_text.set(state['message'] or {'empty':'Ready', 'idle':'Login required', 'ready':'Ready'}.get(phase, phase.capitalize()))

    def _render_tabs(self, jobs, state, locked):
        signature = (locked, self.view_id, state['current_id'], state['phase'], tuple((j.id, j.state, j.path.name) for j in jobs))
        if signature == self.tab_signature:
            return
        self.tab_signature = signature
        old_tab_scroll = self.tabs_canvas.xview()
        for child in self.tabs.winfo_children():
            child.destroy()
        for job in jobs:
            color = TINT if job.id == self.view_id else '#F0F1F3'
            tab = ttk.Frame(self.tabs)
            tab.pack(side='left', padx=(0, 4))
            text = job.path.name
            if len(text) > 27:
                text = text[:24] + '…'
            if job.state == 'Uploaded':
                text += ' ✓'
            label = ttk.Label(tab, text=text, background=color, foreground=GREEN if job.state == 'Uploaded' else TEXT,
                              padding=(10, 8), cursor='hand2')
            label.pack(fill='x')
            label.bind('<Button-1>', lambda e, ident=job.id: self._choose_tab(ident))
            label.bind('<Button-3>', lambda e, ident=job.id: self._tab_menu(e, ident))
            Tooltip(label, job.path.name + '\n' + job.state)
            underline = Canvas(tab, width=1, height=3, bg=YELLOW if state['current_id'] == job.id and state['phase'] in {'running','pausing','paused','blocked','reauth'} else color, highlightthickness=0)
            underline.pack(fill='x')
        add = ttk.Button(self.tabs, text='+' if jobs else '+ Open CSV file', command=self._add_files)
        add.pack(side='left', padx=(2, 0))
        if locked:
            add.state(['disabled'])
        self.tabs.update_idletasks()
        self.tabs_canvas.configure(scrollregion=self.tabs_canvas.bbox('all'))
        if old_tab_scroll:
            self.tabs_canvas.xview_moveto(old_tab_scroll[0])

    def _tabs_changed(self, _event=None):
        bounds = self.tabs_canvas.bbox('all')
        self.tabs_canvas.configure(scrollregion=bounds)
        if bounds and bounds[2] > self.tabs_canvas.winfo_width():
            self.tab_scroll.grid()
        else:
            self.tab_scroll.grid_remove()
            self.tabs_canvas.xview_moveto(0)

    def _table(self):
        job = self._view()
        if self.table_job_id is not None:
            self.table_views[self.table_job_id] = (self.tree.focus(), self.tree.selection(), self.tree.yview())
        self.table_job_id = job.id if job else None
        focused, selected, y = self.table_views.get(self.table_job_id, ('', (), (0,1)))
        self.tree.delete(*self.tree.get_children())
        self.empty_label.grid_remove() if job else self.empty_label.grid()
        if job is None:
            self.tree.grid_remove()
            self.vertical.grid_remove()
            self.horizontal.grid_remove()
            self.table_header.grid_remove()
            self.job_count_text.set('')
            self.select_all.state(['disabled'])
            return
        self.tree.grid()
        self.vertical.grid()
        self.horizontal.grid()
        self.table_header.grid()
        selectable = [r for r in job.rows if r.row.enabled and r.count]
        count = sum(r.selected for r in selectable)
        self.all_var.set(1 if selectable and count == len(selectable) else 0)
        self.select_all.state(['alternate' if 0 < count < len(selectable) else '!alternate'])
        self.select_all.state(['disabled' if self.state['started'] or self.task_busy else '!disabled'])
        self.job_count_text.set(f'{job.successful_count} / {job.selected_count} images' if self.state['started'] else f'{job.selected_count} selected')
        for row in job.rows:
            status = row.status if row.selected else 'Excluded'
            if status == 'Waiting' and self.state['phase'] == 'paused' and job.id == self.state['current_id'] and row.row.row_number == self.state['current_row']:
                status = 'Paused'
            values = ('☑' if row.selected else '☐', row.row.row_number, row.row.tier, row.row.department, row.row.shift, row.row.metric, row.count, '✓ Uploaded' if status == 'Uploaded' else status)
            self.tree.insert('', 'end', iid=str(row.row.row_number), values=values, tags=(status,))
        if focused and self.tree.exists(focused):
            self.tree.focus(focused)
        kept = [iid for iid in selected if self.tree.exists(iid)]
        if kept:
            self.tree.selection_set(kept)
        if y:
            self.tree.yview_moveto(y[0])

    def _timer(self):
        elapsed = self.state['elapsed'] + (time.monotonic()-self.state_at if self.state['clock_running'] else 0)
        seconds = max(0, int(elapsed))
        self.timer_text.set(f'{seconds//3600:02d}:{seconds//60%60:02d}:{seconds%60:02d}' if seconds>=3600 else f'{seconds//60:02d}:{seconds%60:02d}')

    def _choose_tab(self, ident):
        self.view_id = ident
        self._render()

    def _add_files(self):
        if self.state['started'] or self.task_busy:
            return
        paths = filedialog.askopenfilenames(title='Open CSV file', initialdir=picker_directory(), filetypes=[('CSV files','*.csv')])
        if not paths:
            return
        try:
            remember_directory(Path(paths[0]).parent)
        except OSError:
            self._log('Could not remember the file-picker directory.')
        def load():
            for path in paths:
                try:
                    job = Job.load(Path(path))
                    self.engine.add(job)
                except Exception as exc:
                    self.events.put(('error', sanitize(str(exc))))
        self._submit(load)

    def _main(self):
        phase = self.state['phase']
        if phase in {'idle','empty'}:
            self._submit(self.engine.prepare)
        elif phase == 'ready':
            self._submit(self.engine.run)
        elif phase == 'running':
            self.engine.request_pause()
        elif phase in {'paused','reauth'}:
            self.engine.resume()
        elif phase == 'blocked':
            if messagebox.askyesno('Verify upload result', 'Open the assigned board and check every image in the current row.\n\nHave you verified that ALL those images were saved correctly?\n\nChoose No if any result is uncertain.', default='no'):
                self.engine.confirm_unknown_saved()
        elif phase == 'finished' and self.state['can_retry']:
            self._submit(lambda: self.engine.run(retry=True))
        elif phase in {'finished','cancelled'}:
            self._new()

    def _select_all(self):
        job = self._view()
        if job and not self.task_busy:
            self.engine.select(job.id, None, bool(self.all_var.get()))

    def _tree_click(self, event):
        if self.tree.identify_region(event.x, event.y) == 'cell' and self.tree.identify_column(event.x) == '#1':
            self._toggle_row(self.tree.identify_row(event.y))
            return 'break'

    def _tree_space(self, _event):
        self._toggle_row(self.tree.focus())
        return 'break'

    def _toggle_row(self, iid):
        job = self._view()
        if not job or not iid or self.task_busy or self.state['started']:
            return
        row = next(r for r in job.rows if str(r.row.row_number) == iid)
        self.engine.select(job.id, row.row.row_number, not row.selected)

    def _tab_menu(self, event, ident):
        if self.task_busy or self.state['started']:
            return
        menu = Menu(self, tearoff=False)
        menu.add_command(label='Remove from queue', command=lambda: self._submit(lambda: self.engine.remove(ident)))
        menu.tk_popup(event.x_root, event.y_root)

    def _row_hint(self, _event=None):
        job = self._view()
        if job and self.tree.selection():
            row = next((r for r in job.rows if str(r.row.row_number) == self.tree.selection()[0]), None)
            if row and row.reason:
                self.footer_text.set(row.reason)

    def _row_menu(self, event):
        iid = self.tree.identify_row(event.y)
        if iid:
            self.tree.selection_set(iid)
            menu = Menu(self, tearoff=False)
            menu.add_command(label='Inspect row', command=self._inspect_row)
            menu.tk_popup(event.x_root, event.y_root)

    def _inspect_row(self, _event=None):
        job = self._view()
        if not job or not self.tree.selection():
            return
        row = next(r for r in job.rows if str(r.row.row_number) == self.tree.selection()[0])
        lines = [f'Row {row.row.row_number} — {row.status}', row.reason or 'No diagnostic issues recorded.']
        lines += [f'Image {i}: {p.name if p else "Not set"}' for i,p in enumerate(row.row.image_paths,1)]
        messagebox.showinfo('Row details', '\n'.join(lines))

    def _skip(self):
        if messagebox.askyesno('Skip current board?', 'Skip the remaining rows of the execution-current board?\nAlready uploaded images will be retained.', default='no'):
            self.engine.request_skip()

    def _cancel(self):
        if messagebox.askyesno('Cancel all uploads?', 'Cancel the remaining queue and keep the results?', default='no'):
            self.engine.request_cancel()

    def _new(self):
        self._submit(self.engine.clear)

    def _toggle_log(self):
        self.details_visible = not self.details_visible
        if self.details_visible:
            self.log_frame.grid(row=2, column=0, sticky='ew')
        else:
            self.log_frame.grid_remove()
        self.log_toggle.configure(text=('⌄' if self.details_visible else '›')+' Activity log')

    def _sharing_notice(self):
        return messagebox.askokcancel('Review diagnostics before sharing', 'Diagnostics can contain filenames or operational details. Review them before sharing outside your organization.')

    def _copy_log(self):
        if self._sharing_notice():
            self.clipboard_clear()
            self.clipboard_append('\n'.join(sanitize(line) for line in self.activity))

    def _export_log(self):
        if not self._sharing_notice():
            return
        path = filedialog.asksaveasfilename(title='Export diagnostics', defaultextension='.txt', initialfile='PD-Uploader-diagnostics.txt')
        if path:
            try:
                Path(path).write_text('\n'.join(sanitize(line) for line in self.activity), encoding='utf-8')
            except OSError:
                messagebox.showerror('Export', 'Could not write the diagnostics file.')

    def _on_close(self):
        if self.closing:
            return
        if self.close_pending:
            # Deliberate second close permits exit even if the server never responds.
            if messagebox.askyesno('Exit while waiting?', 'The server has not confirmed the current operation. Closing cannot cancel a server-side save.\n\nExit and retain an unknown result?', default='no'):
                self._shutdown()
            return
        if self.state['phase'] in {'running','pausing'}:
            self.exit_was_running = self.state['phase'] == 'running'
            self.close_pending = True
            self.engine.request_pause()
        elif self.state['started'] and self.state['phase'] in {'paused','blocked','reauth'}:
            self.exit_was_running = False
            self._confirm_exit()
        else:
            self._shutdown()

    def _confirm_exit(self):
        if messagebox.askyesno('Exit PD Uploader?', 'An upload is in progress. Are you sure you want to exit?', default='no'):
            self._shutdown()
        elif self.exit_was_running and self.state['phase'] == 'paused':
            self.engine.resume()

    def _shutdown(self):
        self.closing = True
        self.engine.shutdown.set()
        self.engine.interrupt.set()
        self.engine.request_cancel()
        self.tasks.put(None)
        self.footer_text.set('Closing managed browser sessions…')
        self.main_button.state(['disabled'])


def main():
    UploaderApp().mainloop()
