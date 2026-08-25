# -*- coding: utf-8 -*-
from __future__ import annotations
import json, threading, traceback, textwrap, os
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.dates as mdates
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from .config import APP_NAME,VERSION,TIMEZONE,OUTPUT_DIR,SETTINGS_FILE,PRESSURE_LEVELS
from .pipeline import load_data_for_date
from .archive_service import load_archive_day, update_day, bundle_has_plot_data
from .archive import load_bundle, missing_sources, read_origin_marker
from .config import LOCATION_NAME, LOCATION_SLUG, TIMEZONE, LAT, LON
from .inversion_engine import inversion_label,calculate_profile_metrics
from .weather_sources import haversine_km
from .logger import LOGGER
from .location_service import add_and_activate_location, list_locations, LocationError
from .runtime_location import activate_runtime_location
from .remote_archive import fetch_remote_day

class InversionApp(tk.Tk):
    DEFAULT_SETTINGS = {
        "geometry": "1450x900",
        "user_mode": "normal",
        "display": {
            "model": True,
            "gradient": True,
            "icon_d2": True,
            "kit": True,
            "radiosonde": True,
            "legend": True,
            "figure_info": True
        },
        "sources": {
            "icon_d2_update": True,
            "kit_update": True,
            "radiosonde_update": True
        },
        "advanced": {
            "show_side_panel": True,
            "show_log": True
        }
    }

    def __init__(self):
        super().__init__()
        self.title(f'{APP_NAME} – v{VERSION}')
        self.minsize(980,680)
        self.bundle=None
        self.loading=False
        self.selected_date=datetime.now(ZoneInfo(TIMEZONE)).date()
        self.settings_data={}
        self.data_origin='Noch keine Daten'
        self.data_origin_detail=''
        self.source_origin_map={}
        self._nav_press_after_id=None
        self._nav_long_press_fired=False
        self._nav_press_delta=0
        self._nav_long_press_ms=650
        self.protocol('WM_DELETE_WINDOW',self.on_close)
        self.load_settings()
        self.build_gui()
        self.apply_user_mode(redraw=False)
        self.draw_empty_plot()
        self.after(300,self.start_update)

    def _deep_merge_settings(self, base, override):
        result={}
        for key,value in base.items():
            if isinstance(value,dict):
                candidate=override.get(key,{}) if isinstance(override,dict) else {}
                result[key]=self._deep_merge_settings(value,candidate if isinstance(candidate,dict) else {})
            else:
                result[key]=override.get(key,value) if isinstance(override,dict) else value
        if isinstance(override,dict):
            for key,value in override.items():
                if key not in result:
                    result[key]=value
        return result

    def load_settings(self):
        raw={}
        try:
            if SETTINGS_FILE.exists():
                raw=json.loads(SETTINGS_FILE.read_text(encoding='utf-8'))
                if not isinstance(raw,dict):
                    raw={}
        except Exception:
            LOGGER.exception('settings.json konnte nicht gelesen werden')
            raw={}

        self.settings_data=self._deep_merge_settings(self.DEFAULT_SETTINGS,raw)
        geometry=str(self.settings_data.get('geometry','1450x900'))
        self.geometry(geometry)

    def save_settings(self):
        try:
            if hasattr(self,'mode_var'):
                self.settings_data['user_mode']=self.mode_var.get()
            if hasattr(self,'display_vars'):
                self.settings_data['display']={
                    key:bool(var.get()) for key,var in self.display_vars.items()
                }
            if hasattr(self,'source_vars'):
                self.settings_data['sources']={
                    key:bool(var.get()) for key,var in self.source_vars.items()
                }
            if hasattr(self,'advanced_side_var'):
                self.settings_data.setdefault('advanced',{})['show_side_panel']=bool(
                    self.advanced_side_var.get()
                )

            self.settings_data['geometry']=self.geometry()
            self.settings_data['version']=VERSION
            SETTINGS_FILE.write_text(
                json.dumps(self.settings_data,indent=2,ensure_ascii=False),
                encoding='utf-8'
            )
        except Exception:
            LOGGER.exception('settings.json konnte nicht gespeichert werden')

    def _configure_touch_style(self):
        style=ttk.Style(self)
        # Große Touch-Ziele: auf Windows angenehm, auf Tablet/Android vorbereitet.
        style.configure(
            'Touch.TButton',
            padding=(14,10),
            font=('Segoe UI',11)
        )
        style.configure(
            'TouchAccent.TButton',
            padding=(16,11),
            font=('Segoe UI',11,'bold')
        )
        style.configure(
            'Touch.TCheckbutton',
            padding=(4,7),
            font=('Segoe UI',10)
        )
        style.configure(
            'Touch.TRadiobutton',
            padding=(4,7),
            font=('Segoe UI',10)
        )

    def build_gui(self):
        self._configure_touch_style()
        self.columnconfigure(0,weight=1)
        self.rowconfigure(2,weight=1)

        top=ttk.Frame(self,padding=(10,8,10,5))
        top.grid(row=0,column=0,sticky='ew')
        top.columnconfigure(0,weight=1)
        top.columnconfigure(1,weight=0)

        self.title_label=ttk.Label(
            top,text=f'Tägliche Inversionskurve – {LOCATION_NAME}',
            font=('Segoe UI',16,'bold')
        )
        self.title_label.grid(row=0,column=0,sticky='w')

        self.time_label=ttk.Label(top,text='Noch keine Daten geladen')
        self.time_label.grid(row=0,column=1,sticky='e',padx=(12,0))

        # Fingerfreundliche Hauptleiste: nur häufige Aktionen.
        buttons=ttk.Frame(self,padding=(10,0,10,7))
        buttons.grid(row=1,column=0,sticky='ew')
        buttons.columnconfigure(3,weight=1)

        self.prev_button=ttk.Button(
            buttons,text='◀',width=4,style='Touch.TButton'
        )
        self.prev_button.grid(row=0,column=0,padx=(0,6),sticky='w')
        self._bind_day_step_button(self.prev_button,-1)

        self.today_button=ttk.Button(
            buttons,text='HEUTE',style='Touch.TButton',
            command=self.set_today
        )
        self.today_button.grid(row=0,column=1,padx=6,sticky='w')

        self.next_button=ttk.Button(
            buttons,text='▶',width=4,style='Touch.TButton'
        )
        self.next_button.grid(row=0,column=2,padx=6,sticky='w')
        self._bind_day_step_button(self.next_button,1)

        date_host=ttk.Frame(buttons)
        date_host.grid(row=0,column=3,sticky='ew',padx=(8,12))
        date_host.columnconfigure(0,weight=1)
        self.date_var=tk.StringVar(value=self.selected_date.isoformat())
        self.date_entry=ttk.Entry(
            date_host,textvariable=self.date_var,
            justify='center',font=('Segoe UI',12)
        )
        self.date_entry.grid(row=0,column=0,sticky='ew',ipady=8)

        self.online_button=ttk.Button(
            buttons,text='UPDATE',style='TouchAccent.TButton',
            command=self.start_force_update
        )
        self.online_button.grid(row=0,column=4,padx=6,sticky='e')

        self.save_png_button=ttk.Button(
            buttons,text='PNG',style='Touch.TButton',
            command=self.save_png,state='normal'
        )
        self.save_png_button.grid(row=0,column=5,padx=6,sticky='e')

        self.menu_button=ttk.Button(
            buttons,text='⋮',width=4,style='Touch.TButton',
            command=self.show_settings_panel
        )
        self.menu_button.grid(row=0,column=6,padx=(6,0),sticky='e')

        # Legacy/internal button handles. Archive loading is normally triggered
        # by date navigation; explicit archive load is available in ⋮.
        self.update_button=self.online_button
        self.save_csv_button=ttk.Button(
            buttons,text='CSV',command=self.save_csv,state='disabled'
        )
        self.save_csv_button.grid_remove()

        self.main_pane=ttk.Panedwindow(self,orient=tk.HORIZONTAL)
        self.main_pane.grid(row=2,column=0,sticky='nsew',padx=10,pady=(0,8))

        self.plot_frame=ttk.Frame(self.main_pane)
        self.main_pane.add(self.plot_frame,weight=7)
        self.plot_frame.columnconfigure(0,weight=1)
        self.plot_frame.rowconfigure(0,weight=1)

        self.figure=Figure(figsize=(10,6),dpi=100)
        self.ax=self.figure.add_subplot(111)
        self.canvas=FigureCanvasTkAgg(self.figure,master=self.plot_frame)
        self.canvas.get_tk_widget().grid(row=0,column=0,sticky='nsew')

        tf=ttk.Frame(self.plot_frame)
        tf.grid(row=1,column=0,sticky='ew')
        self.toolbar=NavigationToolbar2Tk(self.canvas,tf,pack_toolbar=False)
        self.toolbar.update()
        self.toolbar.pack(side='left')

        self.quality_class_var=tk.StringVar(value='X')
        self.quality_text_var=tk.StringVar(value='Noch nicht bewertet')
        self.canvas.mpl_connect('button_press_event', self.on_plot_click)

        self.side_panel=ttk.Frame(self.main_pane,padding=(10,0,0,0))
        self.main_pane.add(self.side_panel,weight=3)
        self.side_panel.columnconfigure(0,weight=1)
        self.side_panel.rowconfigure(2,weight=1)

        self._status(self.side_panel)
        self._values(self.side_panel)

        self.source_log_pane=ttk.Panedwindow(self.side_panel,orient=tk.VERTICAL)
        self.source_log_pane.grid(row=2,column=0,sticky='nsew')
        source_host=ttk.Frame(self.source_log_pane)
        log_host=ttk.Frame(self.source_log_pane)
        self.source_log_pane.add(source_host,weight=2)
        self.source_log_pane.add(log_host,weight=3)
        source_host.columnconfigure(0,weight=1)
        source_host.rowconfigure(0,weight=1)
        log_host.columnconfigure(0,weight=1)
        log_host.rowconfigure(0,weight=1)
        self._sources(source_host)
        self._logbox(log_host)

        footer=ttk.Frame(self,padding=(10,0,10,8))
        footer.grid(row=3,column=0,sticky='ew')
        footer.columnconfigure(0,weight=1)
        self.progress=ttk.Progressbar(footer,mode='indeterminate')
        self.progress.grid(row=0,column=0,sticky='ew')
        ttk.Label(footer,text=f'Version {VERSION}').grid(row=0,column=1,padx=(10,0))

        self.mode_var=tk.StringVar(value=str(self.settings_data.get('user_mode','normal')))
        display=self.settings_data.get('display',{})
        self.display_vars={
            'model':tk.BooleanVar(value=bool(display.get('model',True))),
            'gradient':tk.BooleanVar(value=bool(display.get('gradient',True))),
            'icon_d2':tk.BooleanVar(value=bool(display.get('icon_d2',True))),
            'kit':tk.BooleanVar(value=bool(display.get('kit',True))),
            'radiosonde':tk.BooleanVar(value=bool(display.get('radiosonde',True))),
            'legend':tk.BooleanVar(value=bool(display.get('legend',True))),
            'figure_info':tk.BooleanVar(value=bool(display.get('figure_info',True))),
        }
        sources=self.settings_data.get('sources',{})
        self.source_vars={
            'icon_d2_update':tk.BooleanVar(value=bool(sources.get('icon_d2_update',True))),
            'kit_update':tk.BooleanVar(value=bool(sources.get('kit_update',True))),
            'radiosonde_update':tk.BooleanVar(value=bool(sources.get('radiosonde_update',True))),
        }
        self.advanced_side_var=tk.BooleanVar(
            value=bool(self.settings_data.get('advanced',{}).get('show_side_panel',True))
        )

    def _bind_day_step_button(self, button, delta):
        """
        Kurz drücken: +/-1 Tag.
        Lang drücken (>= _nav_long_press_ms): +/-7 Tage.
        Für Maus und Touch geeignet; der lange Druck löst NICHT zusätzlich
        den kurzen Schritt aus.
        """
        button.bind(
            '<ButtonPress-1>',
            lambda event,d=delta:self._day_step_press(d),
            add='+'
        )
        button.bind(
            '<ButtonRelease-1>',
            lambda event,d=delta:self._day_step_release(d),
            add='+'
        )
        button.bind(
            '<Leave>',
            lambda event:self._day_step_leave(),
            add='+'
        )

    def _day_step_press(self, delta):
        self._cancel_day_step_timer()
        self._nav_long_press_fired=False
        self._nav_press_delta=int(delta)
        self._nav_press_after_id=self.after(
            self._nav_long_press_ms,
            self._day_step_long_fire
        )

    def _day_step_long_fire(self):
        self._nav_press_after_id=None
        self._nav_long_press_fired=True
        delta=7 if self._nav_press_delta > 0 else -7
        self.shift_date(delta)

    def _day_step_release(self, delta):
        self._cancel_day_step_timer()
        if not self._nav_long_press_fired:
            self.shift_date(1 if int(delta) > 0 else -1)
        self._nav_long_press_fired=False
        self._nav_press_delta=0

    def _day_step_leave(self):
        # Verlassen des Buttons vor Ablauf = kein Langdruck.
        # Der normale ButtonRelease verarbeitet danach ggf. den Kurzschritt.
        self._cancel_day_step_timer()

    def _cancel_day_step_timer(self):
        if self._nav_press_after_id is not None:
            try:
                self.after_cancel(self._nav_press_after_id)
            except Exception:
                pass
            self._nav_press_after_id=None

    def _pane_contains(self, widget):
        try:
            return str(widget) in [str(x) for x in self.main_pane.panes()]
        except Exception:
            return False

    def apply_user_mode(self, redraw=True):
        mode=self.mode_var.get() if hasattr(self,'mode_var') else 'normal'
        show_side=(mode=='advanced' and bool(self.advanced_side_var.get()))

        if show_side:
            if not self._pane_contains(self.side_panel):
                self.main_pane.add(self.side_panel,weight=3)
        else:
            if self._pane_contains(self.side_panel):
                self.main_pane.forget(self.side_panel)

        if redraw and getattr(self,'bundle',None) is not None:
            try:
                self.draw_plot()
            except Exception:
                LOGGER.exception('Plot konnte nach Moduswechsel nicht neu gezeichnet werden')
        self.save_settings()

    def _settings_changed(self):
        self.save_settings()
        self.apply_user_mode(redraw=False)
        if getattr(self,'bundle',None) is not None:
            try:
                self.draw_plot()
            except Exception:
                LOGGER.exception('Plot konnte nach Einstellungsänderung nicht neu gezeichnet werden')

    def _requested_update_sources(self):
        # Kernquellen bleiben ortsunabhängig aktiv.
        wanted={'dwd','profile'}
        if self.source_vars['icon_d2_update'].get():
            wanted.add('icon_d2')
        if self.source_vars['kit_update'].get():
            wanted.add('kit_mast')
        if self.source_vars['radiosonde_update'].get():
            wanted.add('sonde')
        return wanted

    def show_settings_panel(self):
        win=tk.Toplevel(self)
        win.title('⋮ Einstellungen')
        win.geometry('620x720')
        win.minsize(520,560)
        win.transient(self)

        outer=ttk.Frame(win,padding=12)
        outer.pack(fill='both',expand=True)
        outer.columnconfigure(0,weight=1)
        outer.rowconfigure(0,weight=1)

        canvas=tk.Canvas(outer,highlightthickness=0)
        scroll=ttk.Scrollbar(outer,orient='vertical',command=canvas.yview)
        host=ttk.Frame(canvas)
        host.columnconfigure(0,weight=1)
        host_id=canvas.create_window((0,0),window=host,anchor='nw')
        canvas.configure(yscrollcommand=scroll.set)
        canvas.grid(row=0,column=0,sticky='nsew')
        scroll.grid(row=0,column=1,sticky='ns')

        def sync_region(event=None):
            canvas.configure(scrollregion=canvas.bbox('all'))
            try:
                canvas.itemconfigure(host_id,width=canvas.winfo_width())
            except Exception:
                pass

        def on_mousewheel(event):
            # Windows/macOS: event.delta; Linux/X11: Button-4/5 below.
            delta=getattr(event,'delta',0)
            if delta:
                steps=-int(delta/120) if abs(delta) >= 120 else (-1 if delta > 0 else 1)
                canvas.yview_scroll(steps,'units')
            return 'break'

        def on_button4(event):
            canvas.yview_scroll(-1,'units')
            return 'break'

        def on_button5(event):
            canvas.yview_scroll(1,'units')
            return 'break'

        def bind_mousewheel(event=None):
            canvas.bind_all('<MouseWheel>',on_mousewheel)
            canvas.bind_all('<Button-4>',on_button4)
            canvas.bind_all('<Button-5>',on_button5)

        def unbind_mousewheel(event=None):
            try:
                canvas.unbind_all('<MouseWheel>')
                canvas.unbind_all('<Button-4>')
                canvas.unbind_all('<Button-5>')
            except Exception:
                pass

        host.bind('<Configure>',sync_region)
        canvas.bind('<Configure>',sync_region)
        win.bind('<Enter>',bind_mousewheel)
        win.bind('<Leave>',unbind_mousewheel)
        win.protocol(
            'WM_DELETE_WINDOW',
            lambda:(unbind_mousewheel(),win.destroy())
        )

        location_box=ttk.LabelFrame(host,text='Ort',padding=10)
        location_box.grid(row=0,column=0,sticky='ew',pady=(0,10))
        location_box.columnconfigure(0,weight=1)

        ttk.Label(
            location_box,
            text=(
                f'Aktiver Ort: {LOCATION_NAME}  '
                f'({LAT:.4f}, {LON:.4f})'
            ),
            wraplength=540,justify='left'
        ).grid(row=0,column=0,columnspan=2,sticky='w',pady=(0,7))

        active_key,known_locations=list_locations()
        ttk.Label(location_box,text='Vorhandenen Ort auswählen:').grid(
            row=1,column=0,columnspan=2,sticky='w'
        )
        self.location_select_var=tk.StringVar(value=active_key or LOCATION_NAME)
        location_combo=ttk.Combobox(
            location_box,textvariable=self.location_select_var,
            values=list(known_locations.keys()),state='readonly',font=('Segoe UI',11)
        )
        location_combo.grid(row=2,column=0,sticky='ew',ipady=5,padx=(0,6),pady=(5,7))
        ttk.Button(
            location_box,text='Ort wechseln',style='Touch.TButton',
            command=lambda:self._switch_location_runtime(self.location_select_var.get(),win)
        ).grid(row=2,column=1,sticky='ew',pady=(5,7))
        ttk.Separator(location_box,orient='horizontal').grid(
            row=3,column=0,columnspan=2,sticky='ew',pady=(3,8)
        )
        ttk.Label(location_box,text='Neuen Ort nur mit Ortsnamen eingeben:').grid(
            row=4,column=0,columnspan=2,sticky='w'
        )
        self.location_name_var=tk.StringVar(value='')
        location_entry=ttk.Entry(
            location_box,
            textvariable=self.location_name_var,
            font=('Segoe UI',11)
        )
        location_entry.grid(
            row=5,column=0,sticky='ew',ipady=7,padx=(0,6),pady=(5,5)
        )

        def add_location_from_name():
            name=self.location_name_var.get().strip()
            if not name:
                messagebox.showwarning(
                    'Ort','Bitte einen Ortsnamen eingeben.',parent=win
                )
                return
            try:
                key,resolved=add_and_activate_location(name,country_code='DE')
            except LocationError as exc:
                messagebox.showerror(
                    'Ort konnte nicht angelegt werden',str(exc),parent=win
                )
                return
            self.log(
                f"Neuer Ort '{key}' gespeichert: "
                f"{resolved['latitude']:.5f}, {resolved['longitude']:.5f}"
            )
            self._switch_location_runtime(key,win)

        ttk.Button(
            location_box,
            text='Ort hinzufügen / aktivieren',
            style='Touch.TButton',
            command=add_location_from_name
        ).grid(row=5,column=1,sticky='ew',pady=(5,5))

        ttk.Label(
            location_box,
            text=(
                'Die Koordinaten, Höhe und Zeitzone werden automatisch über '
                'die Ortsauflösung bestimmt. DWD-Bodenstationen werden nur '
                'innerhalb des für den Ort definierten Radius verwendet. '
                'Der Ortswechsel erfolgt sofort ohne Programmneustart.'
            ),
            wraplength=540,justify='left'
        ).grid(row=6,column=0,columnspan=2,sticky='w',pady=(4,0))

        mode_box=ttk.LabelFrame(host,text='Bedienmodus',padding=10)
        mode_box.grid(row=1,column=0,sticky='ew',pady=(0,10))
        ttk.Radiobutton(
            mode_box,text='Normal – große, einfache Ansicht',
            variable=self.mode_var,value='normal',
            style='Touch.TRadiobutton',
            command=self._settings_changed
        ).pack(anchor='w',fill='x')
        ttk.Radiobutton(
            mode_box,text='Advanced User – Diagnosebereich und Detailfunktionen',
            variable=self.mode_var,value='advanced',
            style='Touch.TRadiobutton',
            command=self._settings_changed
        ).pack(anchor='w',fill='x')

        display_box=ttk.LabelFrame(host,text='Display',padding=10)
        display_box.grid(row=2,column=0,sticky='ew',pady=(0,10))
        display_items=[
            ('model','Modell-/DWD-Kurve anzeigen'),
            ('gradient','rechten Modellgradienten anzeigen'),
            ('icon_d2','ICON-D2 anzeigen'),
            ('kit','KIT-Mast anzeigen'),
            ('radiosonde','Radiosonde anzeigen'),
            ('legend','Kurvenlegende anzeigen'),
            ('figure_info','Status / Qualität / Tageswerte im PNG anzeigen'),
        ]
        for key,label in display_items:
            ttk.Checkbutton(
                display_box,text=label,variable=self.display_vars[key],
                style='Touch.TCheckbutton',
                command=self._settings_changed
            ).pack(anchor='w',fill='x')

        source_box=ttk.LabelFrame(host,text='Datenabruf',padding=10)
        source_box.grid(row=3,column=0,sticky='ew',pady=(0,10))
        source_items=[
            ('icon_d2_update','ICON-D2 beim Update abrufen'),
            ('kit_update','KIT-Mast beim Update abrufen'),
            ('radiosonde_update','Radiosonde beim Update abrufen'),
        ]
        for key,label in source_items:
            ttk.Checkbutton(
                source_box,text=label,variable=self.source_vars[key],
                style='Touch.TCheckbutton',
                command=self._settings_changed
            ).pack(anchor='w',fill='x')
        ttk.Label(
            source_box,
            text=(
                'DWD-Boden und das primäre Vertikalprofil bleiben Kernquellen. '
                'Deaktivierte Zusatzquellen werden beim Update nicht neu abgerufen; '
                'bereits archivierte Daten werden nicht gelöscht.'
            ),
            wraplength=540,justify='left'
        ).pack(anchor='w',pady=(6,0))

        adv_box=ttk.LabelFrame(host,text='Advanced User',padding=10)
        adv_box.grid(row=4,column=0,sticky='ew',pady=(0,10))
        ttk.Checkbutton(
            adv_box,text='rechten Diagnosebereich anzeigen',
            variable=self.advanced_side_var,
            style='Touch.TCheckbutton',
            command=self._settings_changed
        ).pack(anchor='w',fill='x')
        ttk.Label(
            adv_box,
            text='Im Normal-Modus wird der rechte Bereich grundsätzlich ausgeblendet.',
            wraplength=540,justify='left'
        ).pack(anchor='w',pady=(4,0))

        action_box=ttk.LabelFrame(host,text='Aktionen / Export',padding=10)
        action_box.grid(row=5,column=0,sticky='ew',pady=(0,10))
        action_box.columnconfigure((0,1),weight=1)

        ttk.Button(
            action_box,text='Archiv laden',style='Touch.TButton',
            command=lambda:(win.destroy(),self.start_archive_load())
        ).grid(row=0,column=0,sticky='ew',padx=(0,5),pady=5)
        ttk.Button(
            action_box,text='CSV speichern',style='Touch.TButton',
            command=self.save_csv
        ).grid(row=0,column=1,sticky='ew',padx=(5,0),pady=5)
        ttk.Button(
            action_box,text='Selbsttest',style='Touch.TButton',
            command=self.run_selftest
        ).grid(row=1,column=0,sticky='ew',padx=(0,5),pady=5)
        ttk.Button(
            action_box,text='Radiosonde Details',style='Touch.TButton',
            command=self.show_radiosonde_details
        ).grid(row=1,column=1,sticky='ew',padx=(5,0),pady=5)
        ttk.Button(
            action_box,text='KIT-Mast Details',style='Touch.TButton',
            command=self.show_kit_mast_details
        ).grid(row=2,column=0,columnspan=2,sticky='ew',pady=5)

        nav_box=ttk.LabelFrame(host,text='Schnellnavigation',padding=10)
        nav_box.grid(row=6,column=0,sticky='ew',pady=(0,10))
        nav_box.columnconfigure((0,1),weight=1)
        ttk.Button(
            nav_box,text='−7 Tage',style='Touch.TButton',
            command=lambda:(win.destroy(),self.shift_date(-7))
        ).grid(row=0,column=0,sticky='ew',padx=(0,5))
        ttk.Button(
            nav_box,text='+7 Tage',style='Touch.TButton',
            command=lambda:(win.destroy(),self.shift_date(7))
        ).grid(row=0,column=1,sticky='ew',padx=(5,0))

        ttk.Button(
            host,text='Schließen',style='Touch.TButton',
            command=lambda:(unbind_mousewheel(),win.destroy())
        ).grid(row=7,column=0,sticky='ew',pady=(4,0))
    def _status(self,p):
        b=ttk.LabelFrame(p,text='Aktueller Status',padding=10); b.grid(row=0,column=0,sticky='ew',pady=(0,8)); b.columnconfigure(1,weight=1); self.status_var=tk.StringVar(value='Bereit'); self.station_var=tk.StringVar(value='–'); ttk.Label(b,text='Status:').grid(row=0,column=0,sticky='w'); ttk.Label(b,textvariable=self.status_var).grid(row=0,column=1,sticky='w',padx=(8,0)); ttk.Label(b,text='DWD-Station:').grid(row=1,column=0,sticky='nw',pady=(5,0)); ttk.Label(b,textvariable=self.station_var,wraplength=340).grid(row=1,column=1,sticky='w',padx=(8,0),pady=(5,0))
        self.data_origin_var=tk.StringVar(value='Noch keine Daten')
        ttk.Label(
            b,
            text='Datenherkunft:',
            font=('Segoe UI',9,'bold')
        ).grid(row=2,column=0,sticky='nw',pady=(7,0))
        ttk.Label(
            b,
            textvariable=self.data_origin_var,
            wraplength=330,
            justify='left'
        ).grid(row=2,column=1,sticky='ew',padx=(8,0),pady=(7,0))


    def _quality_class_definitions(self):
        return {
            'A': 'sehr gute Datenbasis: geeignete Bodenbeobachtung + zwei unabhängige ortsbezogene Vertikalprofile',
            'B': 'gute Datenbasis: geeignete Bodenbeobachtung + mindestens ein ortsbezogenes Vertikalprofil',
            'C': 'eingeschränkte Datenbasis: mindestens ein Vertikalprofil, aber keine geeignete Bodenbeobachtung',
            'X': 'nicht ausreichend: kein brauchbares ortsbezogenes Vertikalprofil',
        }

    def _quality_short_text(self, quality_class):
        return self._quality_class_definitions().get(
            str(quality_class or 'X'),
            'nicht klassifiziert'
        )

    def _quality_info_block_text(self):
        return (
            'A — sehr gute Datenbasis: geeignete Bodenbeobachtung + '
            'zwei unabhängige ortsbezogene Vertikalprofile\n\n'
            'B — gute Datenbasis: geeignete Bodenbeobachtung + '
            'mindestens ein ortsbezogenes Vertikalprofil\n\n'
            'C — eingeschränkte Datenbasis: mindestens ein Vertikalprofil, '
            'aber keine geeignete Bodenbeobachtung\n\n'
            'X — nicht ausreichend: kein brauchbares ortsbezogenes '
            'ortsbezogenes Vertikalprofil\n\n'
            'KIT und Radiosonde: ausschließlich Zusatzinformationen, '
            'unabhängig von A/B/C/X.'
        )

    def _update_quality_display(self):
        quality_class='X'
        detail='Noch nicht bewertet'
        if getattr(self, 'bundle', None) is not None:
            quality_class=str(getattr(self.bundle,'quality_class','X') or 'X')
            detail=getattr(self.bundle,'quality_text','') or self._quality_short_text(quality_class)
        self.quality_class_var.set(quality_class)
        self.quality_text_var.set(detail)

    def _update_station_display(self):
        text='–'
        bundle=getattr(self,'bundle',None)
        station=getattr(bundle,'station_info',None) if bundle is not None else None
        if isinstance(station,dict) and station:
            sid=station.get('station_id')
            name=station.get('name')
            dist=station.get('dist_km')
            parts=[]
            if sid is not None:
                try:
                    parts.append(f"{int(sid):05d}")
                except Exception:
                    parts.append(str(sid))
            if name:
                parts.append(str(name))
            text=" ".join(parts) if parts else '–'
            if isinstance(dist,(int,float)):
                text += f" ({dist:.1f} km)"

            dwd_status=None
            try:
                dwd_status=bundle.source_status.get('dwd')
            except Exception:
                dwd_status=None
            extras=[]
            if dwd_status is not None:
                cov=getattr(dwd_status,'coverage_percent',None)
                age=getattr(dwd_status,'data_age_minutes',None)
                if isinstance(cov,(int,float)):
                    extras.append(f"Abdeckung {cov:.1f}%")
                if isinstance(age,(int,float)):
                    extras.append(f"Alter {age:.0f} min")
                elif getattr(dwd_status,'message','') == 'Messdaten fuer ' + str(getattr(self,'selected_date', '')):
                    extras.append('historischer Tag')
            if extras:
                text += ' | ' + ' | '.join(extras)
        self.station_var.set(text)

    def _figure_footer_lines(self):
        qclass=self.quality_class_var.get() if hasattr(self,'quality_class_var') else 'X'
        qtext=self.quality_text_var.get() if hasattr(self,'quality_text_var') else 'Keine Daten'
        status=self.status_var.get() if hasattr(self,'status_var') else '–'
        station=self.station_var.get() if hasattr(self,'station_var') else '–'
        now_text=self.now_var.get() if hasattr(self,'now_var') else '–'
        max_text=self.max_var.get() if hasattr(self,'max_var') else '–'
        min_text=self.min_var.get() if hasattr(self,'min_var') else '–'

        origin=getattr(self,'data_origin_detail','') or getattr(self,'data_origin','–')
        lines=[
            f"Datenqualität {qclass} — {qtext}",
            f"Datenherkunft: {origin}",
            f"Status: {status} | DWD-Station: {station}",
            f"Aktuell: {now_text}",
            f"Maximum: {max_text}",
            f"Minimum: {min_text}",
            "Klick in Grafik: Klassendefinition der Qualitätsklassen A/B/C/X",
        ]

        wrapped=[]
        for idx, line in enumerate(lines):
            # v0.13.9: etwas breiterer Textbereich im Figure-Footer
            width=136 if idx < 2 else 132
            parts=textwrap.wrap(
                line,
                width=width,
                break_long_words=False,
                break_on_hyphens=False
            ) or [line]
            wrapped.extend(parts)

        if len(wrapped) > 8:
            wrapped = wrapped[:8]
            if len(wrapped[-1]) > 130:
                wrapped[-1] = wrapped[-1][:127] + '...'
        return wrapped

    def _footer_fontsize(self, lines):
        longest=max((len(x) for x in lines), default=0)
        line_count=len(lines)
        if line_count >= 7 or longest > 144:
            return 6.5
        if line_count >= 6 or longest > 132:
            return 6.9
        if line_count >= 5 or longest > 120:
            return 7.4
        return 8.0

    def _draw_figure_footer(self):
        lines=self._figure_footer_lines()
        fontsize=self._footer_fontsize(lines)
        self.figure.text(
            0.010,0.020,
            "\n".join(lines),
            ha='left',
            va='bottom',
            fontsize=fontsize,
            wrap=True
        )

    def _has_exportable_csv_data(self, bundle=None):
        bundle = bundle if bundle is not None else getattr(self,'bundle',None)
        if bundle is None:
            return False
        names=(
            'result_data',
            'sonde_metrics',
            'sonde_profile_data',
            'kit_mast_metrics',
            'icon_d2_data',
            'icon_d2_profile_data',
        )
        for name in names:
            data=getattr(bundle,name,None)
            if data is not None and hasattr(data,'empty') and not data.empty:
                return True
        return False

    def _update_export_buttons(self):
        # PNG bleibt unabhängig von Datenzustand immer verfügbar.
        try:
            self.save_png_button.configure(state='normal')
        except Exception:
            pass

        csv_state='normal' if self._has_exportable_csv_data() else 'disabled'
        try:
            self.save_csv_button.configure(state=csv_state)
        except Exception:
            pass

    def on_plot_click(self,event):
        if event is None or getattr(event,'inaxes',None) is None:
            return
        self.show_quality_info_window()

    def show_quality_info_window(self):
        win=tk.Toplevel(self)
        win.title('Klassendefinition Datenqualität')
        win.geometry('720x520')
        win.minsize(520,360)

        frame=ttk.Frame(win,padding=12)
        frame.pack(fill='both',expand=True)
        frame.columnconfigure(0,weight=1)
        frame.rowconfigure(0,weight=1)

        text=tk.Text(frame,wrap='word',state='normal',padx=8,pady=8)
        text.grid(row=0,column=0,sticky='nsew')
        sb=ttk.Scrollbar(frame,orient='vertical',command=text.yview)
        sb.grid(row=0,column=1,sticky='ns')
        text.configure(yscrollcommand=sb.set)

        intro='Klassendefinition der Datenqualitätsbewertung\n\n'
        text.insert('end',intro)
        text.insert('end',self._quality_info_block_text())
        text.insert(
            'end',
            '\n\nHinweis:\n'
            'KIT und Radiosonde sind nur optionale Zusatzinformationen. '
            'Sie sind nicht Bestandteil der Qualitätsklasse A/B/C/X und '
            'sollen deshalb andere Orte ohne diese Zusatzdaten nicht benachteiligen.'
        )
        text.configure(state='disabled')

    def _values(self,p):
        b=ttk.LabelFrame(p,text='Tageswerte',padding=10); b.grid(row=2,column=0,sticky='ew',pady=(0,8)); self.now_var=tk.StringVar(value='–'); self.max_var=tk.StringVar(value='–'); self.min_var=tk.StringVar(value='–')
        for r,(lab,var) in enumerate([('Aktuell:',self.now_var),('Maximum:',self.max_var),('Minimum:',self.min_var)]): ttk.Label(b,text=lab).grid(row=r,column=0,sticky='w',pady=2); ttk.Label(b,textvariable=var,wraplength=340).grid(row=r,column=1,sticky='w',padx=(8,0),pady=2)
    def _sources(self,p):
        b=ttk.LabelFrame(p,text='Datenquellen',padding=5)
        b.grid(row=0,column=0,sticky='nsew')
        b.columnconfigure(0,weight=1); b.rowconfigure(0,weight=1)

        self.source_text=tk.Text(
            b,
            height=10,
            wrap='word',
            state='disabled',
            padx=6,
            pady=4
        )
        self.source_text.grid(row=0,column=0,sticky='nsew')
        sb=ttk.Scrollbar(b,orient='vertical',command=self.source_text.yview)
        sb.grid(row=0,column=1,sticky='ns')
        self.source_text.configure(yscrollcommand=sb.set)

        # Keep legacy variables for compatibility with older internal code.
        self.dwd_state_var=tk.StringVar(value='Noch nicht geprüft')
        self.profile_state_var=tk.StringVar(value='Noch nicht geprüft')
        self.sonde_state_var=tk.StringVar(value='Noch nicht geprüft')
        self.kit_state_var=tk.StringVar(value='Noch nicht geprüft')
        self.icon_d2_state_var=tk.StringVar(value='Noch nicht geprüft')

        self._render_source_text()

    def _status_text(self, s):
        if s is None:
            return "Noch nicht geprüft"
        state = getattr(s, 'state', '–')
        message = getattr(s, 'message', '') or ''
        detail = getattr(s, 'detail', '') or ''
        text = f"{state} – {message}" if message else str(state)
        if detail:
            text += "\n" + detail
        return text

    def _update_source_status(self):
        """Update all five source-status fields and refresh the source panel."""
        if getattr(self, 'bundle', None) is None:
            return

        self.dwd_state_var.set(
            self._status_text(self.bundle.source_status.get('dwd'))+
            f"\nHerkunft: {self._source_origin_text('dwd')}"
        )
        self.profile_state_var.set(
            self._status_text(self.bundle.source_status.get('profile'))+
            f"\nHerkunft: {self._source_origin_text('profile')}"
        )
        sonde_text=self._status_text(self.bundle.source_status.get('sonde'))
        if not self.source_vars['radiosonde_update'].get():
            sonde_text='ABRUF DEAKTIVIERT – vorhandenes Archiv bleibt erhalten\n' + sonde_text
        sonde_text += f"\nHerkunft: {self._source_origin_text('sonde')}"
        self.sonde_state_var.set(sonde_text)

        kit_text=self._status_text(self.bundle.source_status.get('kit_mast'))
        if not self.source_vars['kit_update'].get():
            kit_text='ABRUF DEAKTIVIERT – vorhandenes Archiv bleibt erhalten\n' + kit_text
        kit_text += f"\nHerkunft: {self._source_origin_text('kit_mast')}"
        self.kit_state_var.set(kit_text)

        icon_status_text = self._status_text(
            self.bundle.source_status.get('icon_d2')
        )
        if not self.source_vars['icon_d2_update'].get():
            icon_status_text='ABRUF DEAKTIVIERT – vorhandenes Archiv bleibt erhalten\n' + icon_status_text
        icon = getattr(self.bundle, 'icon_d2_data', None)
        if (
            icon is not None
            and hasattr(icon, 'empty')
            and not icon.empty
            and 'icon_d2_index' in icon.columns
        ):
            valid = icon['icon_d2_index'].dropna()
            if len(valid) and (valid == 0).all():
                icon_status_text += (
                    "\nHINWEIS: Alle berechneten ICON-D2-Indizes sind 0. "
                    "Rohprofil bitte prüfen."
                )

        self.icon_d2_state_var.set(icon_status_text)
        self._render_source_text()

    def _render_source_text(self):
        if not hasattr(self,'source_text'):
            return
        entries=[
            ('DWD Boden', self.dwd_state_var.get()),
            ('Vertikalprofil', self.profile_state_var.get()),
            ('Idar-Oberstein', self.sonde_state_var.get()),
            ('KIT 200-m-Mast', self.kit_state_var.get()),
            ('ICON-D2 Historical', self.icon_d2_state_var.get()),
        ]
        self.source_text.configure(state='normal')
        self.source_text.delete('1.0','end')
        for i,(name,value) in enumerate(entries):
            if i:
                self.source_text.insert('end','\n')
            self.source_text.insert('end',f'{name}:\n')
            self.source_text.insert('end',f'{value}\n')
        self.source_text.configure(state='disabled')
    def _logbox(self,p):
        b=ttk.LabelFrame(p,text='Protokoll',padding=5)
        b.grid(row=0,column=0,sticky='nsew')
        b.columnconfigure(0,weight=1); b.rowconfigure(0,weight=1)
        self.log_text=tk.Text(b,height=12,wrap='word',state='disabled')
        self.log_text.grid(row=0,column=0,sticky='nsew')
        sb=ttk.Scrollbar(b,orient='vertical',command=self.log_text.yview)
        sb.grid(row=0,column=1,sticky='ns')
        self.log_text.configure(yscrollcommand=sb.set)
    def log(self,text): self.after(0,self._append_log,f"[{datetime.now(ZoneInfo(TIMEZONE)):%H:%M:%S}] {text}\n")
    def _append_log(self,line): self.log_text.configure(state='normal'); self.log_text.insert('end',line); self.log_text.see('end'); self.log_text.configure(state='disabled')
    def _origin_label(self,origin):
        return {
            'LOCAL_ARCHIVE':'Lokales Archiv',
            'LOCAL_ARCHIVE_PARTIAL':'Lokales Archiv (unvollständig)',
            'LOCAL_ARCHIVE_COMPLETE':'Lokales Archiv',
            'LOCAL_ARCHIVE_FROM_GITHUB':'Lokales Archiv – ursprünglich aus GitHub',
            'LOCAL_ARCHIVE_FROM_GITHUB_PARTIAL':'Lokales Archiv – ursprünglich aus GitHub (unvollständig)',
            'LOCAL_ARCHIVE_FROM_ONLINE':'Lokales Archiv – zuletzt online aktualisiert',
            'LOCAL_ARCHIVE_FROM_ONLINE_PARTIAL':'Lokales Archiv – zuletzt online aktualisiert (unvollständig)',
            'GITHUB_ARCHIVE':'GitHub-Archiv',
            'UPDATED_SAFE_MERGE':'Online-Update + Safe-Merge',
        }.get(str(origin),str(origin or 'Unbekannt'))

    def _set_data_origin(self,origin,manifest=None):
        self.data_origin=self._origin_label(origin)
        marker=read_origin_marker(self.selected_date) or {}
        sm=dict(marker.get('source_map') or {})
        if origin=='GITHUB_ARCHIVE':
            sm={k:'GitHub-Archiv' for k in ('dwd','profile','sonde','kit_mast','icon_d2')}
        elif not sm:
            sm={k:'Lokales Archiv' for k in ('dwd','profile','sonde','kit_mast','icon_d2')}
        self.source_origin_map=sm
        saved=(manifest or {}).get('saved_at','–')
        self.data_origin_detail=f"{self.data_origin} | Archivstand: {saved}"
        self.data_origin_var.set(self.data_origin_detail)

    def _source_origin_text(self,key):
        return self.source_origin_map.get(key,self.data_origin or '–')

    def _switch_location_runtime(self,key,settings_window=None):
        global APP_NAME,VERSION,TIMEZONE,OUTPUT_DIR,SETTINGS_FILE,PRESSURE_LEVELS
        global LOCATION_NAME,LOCATION_SLUG,LAT,LON
        global load_data_for_date,load_archive_day,update_day,bundle_has_plot_data
        global load_bundle,missing_sources,read_origin_marker,haversine_km
        global inversion_label,calculate_profile_metrics,fetch_remote_day
        if self.loading:
            messagebox.showwarning('Ortswechsel','Während eines Datenabrufs nicht möglich.',parent=settings_window or self)
            return False
        old_name=LOCATION_NAME
        try:
            mods=activate_runtime_location(key); c=mods['config']
            APP_NAME=c.APP_NAME;VERSION=c.VERSION;TIMEZONE=c.TIMEZONE
            OUTPUT_DIR=c.OUTPUT_DIR;SETTINGS_FILE=c.SETTINGS_FILE;PRESSURE_LEVELS=c.PRESSURE_LEVELS
            LOCATION_NAME=c.LOCATION_NAME;LOCATION_SLUG=c.LOCATION_SLUG;LAT=c.LAT;LON=c.LON
            a=mods['archive'];s=mods['archive_service'];p=mods['pipeline']
            w=mods['weather_sources'];ie=mods['inversion_engine'];r=mods['remote_archive']
            load_data_for_date=p.load_data_for_date;load_archive_day=s.load_archive_day
            update_day=s.update_day;bundle_has_plot_data=s.bundle_has_plot_data
            load_bundle=a.load_bundle;missing_sources=a.missing_sources;read_origin_marker=a.read_origin_marker
            haversine_km=w.haversine_km;inversion_label=ie.inversion_label
            calculate_profile_metrics=ie.calculate_profile_metrics;fetch_remote_day=r.fetch_remote_day
            self.bundle=None;self.source_origin_map={};self.data_origin='Noch keine Daten';self.data_origin_detail=''
            self.title_label.configure(text=f'Tägliche Inversionskurve – {LOCATION_NAME}')
            self.title(f'{APP_NAME} – {LOCATION_NAME} – v{VERSION}')
            self.selected_date=min(self.selected_date,datetime.now(ZoneInfo(TIMEZONE)).date())
            self.date_var.set(self.selected_date.isoformat())
            self.log(f"Ortswechsel ohne Neustart: {old_name} -> {LOCATION_NAME} ({LAT:.5f}, {LON:.5f})")
            self.status_var.set(f'Ort gewechselt: {LOCATION_NAME}')
            self.station_var.set('–');self.now_var.set('–');self.max_var.set('–');self.min_var.set('–')
            self.data_origin_var.set('Noch keine Daten für neuen Ort geladen')
            self.clear_plot(f'{LOCATION_NAME}: Daten werden geladen ...')
            self.load_mode='archive'
            if settings_window is not None: settings_window.destroy()
            self.after(50,self.start_update)
            return True
        except Exception as exc:
            LOGGER.exception('Ortswechsel fehlgeschlagen')
            messagebox.showerror('Ortswechsel fehlgeschlagen',str(exc),parent=settings_window or self)
            return False

    def start_archive_load(self):
        if self.loading:
            return
        self.load_mode='archive'
        self.start_update()

    def start_update(self):
        if self.loading:
            return
        try:
            selected=datetime.strptime(self.date_var.get().strip(),'%Y-%m-%d').date()
        except ValueError:
            messagebox.showerror('Ungültiges Datum','Bitte Datum im Format JJJJ-MM-TT eingeben, z. B. 2026-08-24.',parent=self)
            return
        today=datetime.now(ZoneInfo(TIMEZONE)).date()
        if selected>today:
            messagebox.showwarning('Zukünftiges Datum','Zukünftige Tage können in dieser Version nicht geladen werden.',parent=self)
            return
        self.selected_date=selected
        if not hasattr(self,'load_mode'): self.load_mode='archive'
        self.loading=True
        self.online_button.configure(state='disabled')
        # PNG bleibt auch während Abruf/Fehlerzustand aktiv.
        self.save_png_button.configure(state='normal')
        self.save_csv_button.configure(state='disabled')
        self.status_var.set(f'Daten für {self.selected_date:%d.%m.%Y} werden geladen ...')
        self.progress.start(12)
        self.log(f'Aktualisierung für {self.selected_date} gestartet.')
        threading.Thread(target=self.worker_update,daemon=True).start()
    def start_force_update(self):
        if self.loading:
            return
        self.load_mode='update'
        self.start_update()

    def shift_date(self, days):
        try:
            current = datetime.strptime(self.date_var.get().strip(), "%Y-%m-%d").date()
        except ValueError:
            current = self.selected_date
        new_date = current + timedelta(days=days)
        today = datetime.now(ZoneInfo(TIMEZONE)).date()
        if new_date > today:
            new_date = today
        self.date_var.set(new_date.isoformat())
        self.selected_date = new_date
        self.load_mode='archive'
        self.start_update()

    def set_today(self):
        self.selected_date = datetime.now(ZoneInfo(TIMEZONE)).date()
        self.date_var.set(self.selected_date.isoformat())
        self.load_mode='archive'
        self.start_update()

    def worker_update(self):
        try:
            mode=getattr(self,'load_mode','archive')

            if mode=='update':
                bundle,manifest,origin=update_day(
                    self.selected_date,
                    self.log,
                    only_missing=False,
                    requested_sources=self._requested_update_sources()
                )
                self.load_mode='archive'
                if bundle is None:
                    self.after(
                        0,self.finish_no_data_after_update,
                        self.selected_date,'UPDATE_NO_DATA'
                    )
                    return
                self.after(0,self.finish_update,bundle,manifest,origin)
                return

            # Normal stepping/date load: FIRST local archive only.
            bundle,manifest,origin=load_archive_day(
                self.selected_date,self.log
            )

            # Any usable archived plot data => show immediately, no network.
            if bundle is not None and bundle_has_plot_data(bundle):
                self.load_mode='archive'
                self.after(0,self.finish_update,bundle,manifest,origin)
                return

            self.log(f"Lokales Archiv für {self.selected_date} ohne Plotdaten. GitHub-Archiv wird geprüft.")
            self.after(0,self.clear_plot,f'{LOCATION_NAME}: GitHub-Archiv wird geprüft ...')
            remote_ok,remote_state=fetch_remote_day(self.selected_date,self.log)
            if remote_ok:
                rb,rm,ro=load_archive_day(self.selected_date,self.log)
                if rb is not None and bundle_has_plot_data(rb):
                    self.load_mode='archive'
                    self.after(0,self.finish_update,rb,rm,'GITHUB_ARCHIVE')
                    return
            self.log(f"GitHub-Archiv nicht verwendbar ({remote_state}); direkter Online-Abruf.")
            self.after(0,self.clear_plot,f'{LOCATION_NAME}: Wetterdaten werden online abgerufen ...')
            bundle2,manifest2,origin2=update_day(
                self.selected_date,self.log,only_missing=False
            )
            self.load_mode='archive'

            if bundle2 is None or not bundle_has_plot_data(bundle2):
                self.after(
                    0,self.finish_no_data_after_update,
                    self.selected_date,origin2
                )
                return

            self.after(0,self.finish_update,bundle2,manifest2,origin2)

        except Exception as exc:
            LOGGER.exception('Unerwarteter Gesamtfehler')
            self.log(f'UNERWARTETER FEHLER: {exc}')
            self.log(traceback.format_exc())
            self.load_mode='archive'
            self.after(0,self.finish_error,str(exc))

    def _normalize_bundle_for_display(self,bundle):
        """
        Normalize archived time columns before plotting.
        Returns diagnostic dict and never performs network I/O.
        """
        diag={}
        for name in (
            'dwd_data','profile_data','result_data','sonde_profile_data','sonde_metrics',
            'kit_mast_metrics','icon_d2_data','icon_d2_profile_data'
        ):
            df=getattr(bundle,name,None)
            if df is None or not hasattr(df,'columns'):
                diag[name]=0
                continue
            if 'time' in df.columns:
                try:
                    t=pd.to_datetime(df['time'],errors='coerce',utc=True)
                    if t.notna().any():
                        df=df.copy()
                        df['time']=t.dt.tz_convert(TIMEZONE)
                        df=df[df['time'].notna()].sort_values('time').reset_index(drop=True)
                        setattr(bundle,name,df)
                except Exception as exc:
                    self.log(f'Archiv-Zeitnormalisierung {name}: FEHLER {exc}')
            diag[name]=len(getattr(bundle,name,None)) if getattr(bundle,name,None) is not None else 0
        return diag

    def _has_any_plot_data(self,bundle):
        for name in ('result_data','sonde_metrics','kit_mast_metrics','icon_d2_data'):
            df=getattr(bundle,name,None)
            if df is not None and hasattr(df,'empty') and not df.empty:
                return True
        return False

    def clear_plot(self,message=None):
        """Clear the current chart so no previous day's curve is misleading."""
        try:
            self.figure.clear()
            ax=self.figure.add_subplot(111)
            ax.set_ylim(0,5)
            ax.set_xlim(0,24)
            ax.set_xlabel('Stunde')
            ax.set_ylabel('Inversionsindex 0–5')
            ax.grid(True,alpha=0.3)
            if message:
                ax.set_title(
                f"Inversionsverlauf – {LOCATION_NAME} – {self.selected_date:%d.%m.%Y}"
            )
            ax.text(
                    0.5,0.5,message,
                    transform=ax.transAxes,
                    ha='center',va='center'
                )

            if hasattr(self,'display_vars') and self.display_vars['figure_info'].get():
                self._draw_figure_footer()
            self.figure.subplots_adjust(
                left=0.075,right=0.865,top=0.91,bottom=0.275
            )
            self.ax=ax
            self.canvas.draw_idle()
        except Exception as exc:
            self.log(f"Plot leeren: FEHLER {exc}")

    def finish_update(self,bundle,manifest=None,origin='UNKNOWN'):
        self.loading=False
        self.progress.stop()
        self.online_button.configure(state='normal')
        self.save_png_button.configure(state='normal')
        self.bundle=bundle
        self._set_data_origin(origin,manifest)
        self._update_export_buttons()

        diag=self._normalize_bundle_for_display(bundle)
        self.log(
            "Anzeige-Diagnose: "
            f"Modell={diag.get('result_data',0)} | "
            f"Radiosonde={diag.get('sonde_metrics',0)} | "
            f"KIT={diag.get('kit_mast_metrics',0)} | "
            f"ICON-D2={diag.get('icon_d2_data',0)} | "
            f"ICON-Rohprofil={diag.get('icon_d2_profile_data',0)}"
        )

        self.status_var.set(f'Daten geladen – {origin}')
        self.time_label.configure(
            text=f"Quelle: {origin} | Gespeichert: {(manifest or {}).get('saved_at','–')}"
        )
        self._update_quality_display()
        self._update_station_display()

        # Tageswerte zuerst aktualisieren, damit sie im Figure-Footer
        # mitgespeichert werden können. Fehler bleiben isoliert.
        try:
            self.update_summary()
        except Exception as exc:
            LOGGER.exception("Summary-Fehler")
            self.log(f"Zusammenfassung: FEHLER {exc}")
            self.log(traceback.format_exc())
            self.now_var.set('–')
            self.max_var.set('–')
            self.min_var.set('–')

        # Plot danach zeichnen, damit Qualitäts-, Status- und Tageswerte
        # gemeinsam in die Figure geschrieben werden.
        try:
            if self._has_any_plot_data(bundle):
                self.draw_plot()
                self.log("Archiv-Plot: PASS")
            else:
                self.log("Archiv vorhanden, aber keine darstellbaren Plotdaten gefunden.")
                self.status_var.set(
                    f'Archiv vorhanden, aber keine Plotdaten – {self.selected_date}'
                )
        except Exception as exc:
            LOGGER.exception("Archiv-Plotfehler")
            self.log(f"Archiv-Plot: FEHLER {exc}")
            self.log(traceback.format_exc())
            self.status_var.set(
                f'Archiv vorhanden, Plotdaten konnten nicht dargestellt werden'
            )

        try:
            self._update_source_status()
        except Exception as exc:
            LOGGER.exception("Quellenstatus-Fehler")
            self.log(f"Datenquellen-Anzeige: FEHLER {exc}")
            self.log(traceback.format_exc())

        self.log(f'Aktualisierung beendet. Datenqualität {bundle.quality_class}.')

    def finish_no_archive(self,selected_date,origin):
        self.loading=False
        self.progress.stop()
        self.online_button.configure(state='normal')
        self.save_png_button.configure(state='normal')
        self.bundle=None
        self._update_export_buttons()
        self.quality_class_var.set('X')
        self.quality_text_var.set('Keine Archivdaten für den gewählten Tag')
        self.status_var.set(f'Keine Archivdaten für {selected_date}')
        self.station_var.set('–')
        self.now_var.set('–')
        self.max_var.set('–')
        self.min_var.set('–')
        self.clear_plot(f'Keine Archivdaten für {selected_date}')
        self.time_label.configure(
            text=f"Archiv: {selected_date:%d.%m.%Y} | nicht vorhanden"
        )
        self.log(
            f"Keine lokalen Archivdaten für {selected_date}."
        )

    def finish_no_data_after_update(self,selected_date,origin):
        self.loading=False
        self.progress.stop()
        self.online_button.configure(state='normal')
        self.save_png_button.configure(state='normal')
        self.bundle=None
        self._update_export_buttons()
        self.quality_class_var.set('X')
        self.quality_text_var.set('Keine darstellbaren Plotdaten nach Update verfügbar')
        self.status_var.set(f'Keine Daten für {selected_date} verfügbar')
        self.station_var.set('–')
        self.now_var.set('–')
        self.max_var.set('–')
        self.min_var.set('–')
        self.clear_plot(f'Keine Daten für {selected_date} verfügbar')
        self.time_label.configure(
            text=f"{selected_date:%d.%m.%Y} | nach Update keine Plotdaten"
        )
        self.log(
            f"Automatischer/ausdrücklicher Abruf für {selected_date} beendet, "
            "aber weiterhin keine darstellbaren Plotdaten vorhanden. "
            "Der Plot bleibt deshalb leer."
        )

    def finish_error(self,text):
        self.loading=False
        self.progress.stop()
        self.online_button.configure(state='normal')
        self.save_png_button.configure(state='normal')
        self.status_var.set('Unerwarteter Gesamtfehler')
        # PNG bleibt auch im Fehlerfall aktiv; CSV richtet sich nach eventuell
        # noch vorhandenem Bundle.
        self._update_export_buttons()
        self.station_var.set('–')
        self.now_var.set('–')
        self.max_var.set('–')
        self.min_var.set('–')
        try:
            self.clear_plot('Unerwarteter Gesamtfehler')
        except Exception:
            pass
        messagebox.showerror('Fehler',text,parent=self)
    def draw_empty_plot(self): self.ax.clear(); self.ax.text(.5,.5,'Noch keine Archivdaten geladen',ha='center',va='center',transform=self.ax.transAxes,fontsize=14); self.ax.set_axis_off(); self.canvas.draw_idle()
    def draw_no_data_plot(self): self.figure.clear(); ax=self.figure.add_subplot(111); ax.text(.5,.5,'KEINE BELASTBARE INVERSIONSKURVE VERFÜGBAR\n\nMindestens eine notwendige Datenquelle ist ausgefallen.\nDetails siehe Datenquellen und Protokoll.',ha='center',va='center',transform=ax.transAxes,fontsize=13); ax.set_axis_off(); self.canvas.draw_idle()
    def draw_plot(self):
        model=getattr(self.bundle,'result_data',None)
        sonde=getattr(self.bundle,'sonde_metrics',None)
        kit=getattr(self.bundle,'kit_mast_metrics',None)
        icon=getattr(self.bundle,'icon_d2_data',None)

        self.log(
            f"Plotdaten: Modell={0 if model is None else len(model)} | "
            f"Radiosonde={0 if sonde is None else len(sonde)} | "
            f"KIT={0 if kit is None else len(kit)} | "
            f"ICON-D2={0 if icon is None else len(icon)}"
        )

        self.figure.clear()
        ax1=self.figure.add_subplot(111)
        ax2=ax1.twinx()

        handles=[]
        labels=[]

        show_model=self.display_vars['model'].get()
        show_gradient=self.display_vars['gradient'].get()
        show_sonde=self.display_vars['radiosonde'].get()
        show_kit=self.display_vars['kit'].get()
        show_icon=self.display_vars['icon_d2'].get()

        if model is not None and not model.empty:
            if show_model:
                line_model=ax1.plot(
                    model['time'],
                    model['inversion_index_corrected'],
                    marker='o',
                    linewidth=2,
                    color='blue',
                    label='Modell-/DWD-Inversionsindex'
                )[0]
                handles.append(line_model)
                labels.append('Modell-/DWD-Inversionsindex')

            if show_gradient:
                line_grad=ax2.plot(
                    model['time'],
                    model['max_inv_gradient_K_per_100m'],
                    linestyle='--',
                    linewidth=1.2,
                    color='gray',
                    label='Modell: max. positiver Gradient'
                )[0]
                handles.append(line_grad)
                labels.append('Modell: max. positiver Gradient')

        if show_sonde and sonde is not None and not sonde.empty:
            line_sonde=ax1.plot(
                sonde['time'],
                sonde['radiosonde_index'],
                marker='D',
                linewidth=1.8,
                linestyle='--',
                color='red',
                label='Radiosonde Idar-Oberstein gemessen'
            )[0]
            handles.append(line_sonde)
            labels.append('Radiosonde Idar-Oberstein gemessen')

        if show_kit and kit is not None and not kit.empty:
            line_kit=ax1.plot(
                kit['time'],
                kit['kit_mast_index'],
                marker='^',
                linewidth=2,
                color='orange',
                label='KIT-Mast gemessen (separater Index)'
            )[0]
            handles.append(line_kit)
            labels.append('KIT-Mast gemessen (separater Index)')

        if show_icon and icon is not None and not icon.empty:
            line_icon=ax1.plot(
                icon['time'],
                icon['icon_d2_index'],
                marker='s',
                linewidth=1.6,
                linestyle='-.',
                color='green',
                label='ICON-D2 Historical Forecast (separater Index)'
            )[0]
            handles.append(line_icon)
            labels.append('ICON-D2 Historical Forecast (separater Index)')

        ax1.set_ylim(-.1,5.2)
        ax1.set_ylabel('Inversionsintensität / empirischer Index [0–5]')

        # Rechte Achse bleibt immer geometrisch vorhanden, damit sich das
        # Diagrammformat beim Ein-/Ausblenden nicht ändert.
        ax2.set_ylabel(
            'Modell-Inversionsgradient [K/100 m]' if show_gradient else ''
        )
        if not show_gradient:
            ax2.tick_params(right=False,labelright=False)
            ax2.spines['right'].set_visible(False)

        ax1.set_xlabel(f'Ortszeit {TIMEZONE}')
        ax1.grid(True,alpha=.3)
        ax1.xaxis.set_major_locator(mdates.HourLocator(interval=2))
        ax1.xaxis.set_major_formatter(
            mdates.DateFormatter('%H:%M',tz=ZoneInfo(TIMEZONE))
        )

        ax1.set_title(
            f"Inversionsverlauf – {LOCATION_NAME} – {self.selected_date:%d.%m.%Y}"
        )

        if self.display_vars['legend'].get() and handles:
            ax1.legend(handles,labels,loc='upper right',fontsize=8.0)

        if self.display_vars['figure_info'].get():
            self._draw_figure_footer()

        # FESTES Figure-Layout. Rechts bewusst mehr Platz als v0.13.9,
        # damit die rechte Achsenbeschriftung vollständig lesbar ist.
        # Unten bleibt unabhängig von Textmenge derselbe Bereich reserviert;
        # längerer Text wird über kleinere Schrift kompensiert.
        self.figure.subplots_adjust(
            left=0.075,
            right=0.865,
            top=0.91,
            bottom=0.275
        )

        self.ax=ax1
        self.canvas.draw_idle()

    def update_summary(self):
        model=self.bundle.result_data
        kit=getattr(self.bundle,'kit_mast_metrics',None)

        if model is not None and not model.empty:
            v=model.dropna(subset=['inversion_index_corrected'])
            if not v.empty:
                if self.selected_date==datetime.now(ZoneInfo(TIMEZONE)).date():
                    reference=pd.Timestamp.now(tz=TIMEZONE)
                    current_row=v.loc[(v['time']-reference).abs().idxmin()]
                else:
                    current_row=v.iloc[-1]
                max_row=v.loc[v['inversion_index_corrected'].idxmax()]
                min_row=v.loc[v['inversion_index_corrected'].idxmin()]
                self.now_var.set(
                    f"Modell {float(current_row['inversion_index_corrected']):.2f}/5 "
                    f"({current_row['time']:%H:%M})"
                )
                self.max_var.set(
                    f"Modell {float(max_row['inversion_index_corrected']):.2f}/5 "
                    f"({max_row['time']:%H:%M})"
                )
                self.min_var.set(
                    f"Modell {float(min_row['inversion_index_corrected']):.2f}/5 "
                    f"({min_row['time']:%H:%M})"
                )
        else:
            self.now_var.set('Modell: –')
            self.max_var.set('Modell: –')
            self.min_var.set('Modell: –')

        sonde=getattr(self.bundle,'sonde_metrics',None)
        if sonde is not None and not sonde.empty:
            sv=sonde.dropna(subset=['radiosonde_index'])
            if not sv.empty:
                slast=sv.iloc[-1]
                smax=sv.loc[sv['radiosonde_index'].idxmax()]
                self.now_var.set(
                    self.now_var.get()+
                    f" | Sonde {float(slast['radiosonde_index']):.2f}/5 "
                    f"({slast['time']:%H:%M})"
                )
                self.max_var.set(
                    self.max_var.get()+
                    f" | Sonde {float(smax['radiosonde_index']):.2f}/5 "
                    f"({smax['time']:%H:%M})"
                )

        if kit is not None and not kit.empty:
            kitv=kit.dropna(subset=['kit_mast_index'])
            if not kitv.empty:
                kit_last=kitv.iloc[-1]
                kit_max=kitv.loc[kitv['kit_mast_index'].idxmax()]
                self.now_var.set(
                    self.now_var.get()+
                    f" | KIT {float(kit_last['kit_mast_index']):.2f}/5 "
                    f"({kit_last['time']:%H:%M})"
                )
                self.max_var.set(
                    self.max_var.get()+
                    f" | KIT {float(kit_max['kit_mast_index']):.2f}/5 "
                    f"({kit_max['time']:%H:%M})"
                )


        icon=getattr(self.bundle,'icon_d2_data',None)
        if icon is not None and not icon.empty:
            iv=icon.dropna(subset=['icon_d2_index'])
            if not iv.empty:
                last=iv.iloc[-1]
                mx=iv.loc[iv['icon_d2_index'].idxmax()]
                self.now_var.set(
                    self.now_var.get()+
                    f" | ICON-D2 {float(last['icon_d2_index']):.2f}/5 "
                    f"({last['time']:%H:%M})"
                )
                self.max_var.set(
                    self.max_var.get()+
                    f" | ICON-D2 {float(mx['icon_d2_index']):.2f}/5 "
                    f"({mx['time']:%H:%M})"
                )

    def save_png(self):
        # Absichtlich auch ohne Datenbundle erlaubt: die aktuelle Figure kann
        # dadurch zur Diagnose von Leer-/Fehlerzuständen gespeichert werden.
        try:
            OUTPUT_DIR.mkdir(parents=True,exist_ok=True)
            name=filedialog.asksaveasfilename(
                parent=self,
                title='Diagramm als PNG speichern',
                initialdir=OUTPUT_DIR,
                initialfile=f"{LOCATION_SLUG}_Inversion_{self.selected_date:%Y-%m-%d}.png",
                defaultextension='.png',
                filetypes=[('PNG-Datei','*.png'),('Alle Dateien','*.*')]
            )
            if not name:
                return
            self.figure.savefig(name,dpi=180)
            self.log(f'PNG gespeichert: {name}')
        except Exception as exc:
            LOGGER.exception('PNG-Speichern fehlgeschlagen')
            self.log(f'PNG speichern: FEHLER {exc}')
            messagebox.showerror(
                'PNG speichern',
                f'Die aktuelle Grafik konnte nicht gespeichert werden:\n\n{exc}',
                parent=self
            )
    def save_csv(self):
        if not self.bundle:
            return

        model=self.bundle.result_data
        kit=getattr(self.bundle,'kit_mast_metrics',None)
        icon=getattr(self.bundle,'icon_d2_data',None)
        sonde=getattr(self.bundle,'sonde_metrics',None)
        if ((model is None or model.empty) and (sonde is None or sonde.empty) and (kit is None or kit.empty) and
                (icon is None or icon.empty)):
            return

        OUTPUT_DIR.mkdir(parents=True,exist_ok=True)
        name=filedialog.asksaveasfilename(
            parent=self,
            title='Daten als CSV speichern',
            initialdir=OUTPUT_DIR,
            initialfile=f"{LOCATION_SLUG}_Inversion_{self.selected_date:%Y-%m-%d}.csv",
            defaultextension='.csv',
            filetypes=[('CSV-Datei','*.csv'),('Alle Dateien','*.*')]
        )
        if not name:
            return

        base=Path(name)

        if model is not None and not model.empty:
            df=model.copy()
            df['data_quality_class']=self.bundle.quality_class
            df['data_quality_text']=self.bundle.quality_text
            df.to_csv(base,index=False,encoding='utf-8-sig')
            self.log(f'Modell-CSV gespeichert: {base}')

        if sonde is not None and not sonde.empty:
            sonde_name=base.with_name(base.stem+'_Radiosonde'+base.suffix)
            sonde.to_csv(sonde_name,index=False,encoding='utf-8-sig')
            self.log(f'Radiosonden-CSV gespeichert: {sonde_name}')
            raw_sonde=getattr(self.bundle,'sonde_profile_data',None)
            if raw_sonde is not None and not raw_sonde.empty:
                raw_sonde_name=base.with_name(base.stem+'_Radiosonde_Profile'+base.suffix)
                raw_sonde.to_csv(raw_sonde_name,index=False,encoding='utf-8-sig')
                self.log(f'Radiosonden-Rohprofil-CSV gespeichert: {raw_sonde_name}')

        if kit is not None and not kit.empty:
            kit_name=base.with_name(base.stem+'_KIT_Mast'+base.suffix)
            kit.to_csv(kit_name,index=False,encoding='utf-8-sig')
            self.log(f'KIT-Mast-CSV gespeichert: {kit_name}')

        if icon is not None and not icon.empty:
            icon_name=base.with_name(base.stem+'_ICON_D2'+base.suffix)
            icon.to_csv(icon_name,index=False,encoding='utf-8-sig')
            self.log(f'ICON-D2-CSV gespeichert: {icon_name}')
        raw_icon=getattr(self.bundle,'icon_d2_profile_data',None)
        if raw_icon is not None and not raw_icon.empty:
            raw_name=base.with_name(base.stem+'_ICON_D2_Profile'+base.suffix)
            raw_icon.to_csv(raw_name,index=False,encoding='utf-8-sig')
            self.log(f'ICON-D2-Rohprofil-CSV gespeichert: {raw_name}')

    def run_selftest(self):
        checks=[]
        try:
            checks.append(('Entfernungsfunktion',abs(haversine_km(49,8,49,8))<1e-9)); synthetic=pd.DataFrame({'time':pd.date_range('2026-08-24',periods=2,freq='1h',tz=TIMEZONE),'temperature_2m':[10.,12.],'temperature_1000hPa':[11.,11.5],'geopotential_height_1000hPa':[150.,150.]})
            for p in PRESSURE_LEVELS:
                if f'temperature_{p}hPa' not in synthetic:synthetic[f'temperature_{p}hPa']=np.nan
                if f'geopotential_height_{p}hPa' not in synthetic:synthetic[f'geopotential_height_{p}hPa']=np.nan
            calc=calculate_profile_metrics(synthetic); checks.append(('Inversionsberechnung','inversion_index' in calc.columns)); checks.append(('Indexwerte endlich',np.isfinite(calc['inversion_index']).all())); checks.append(('Qualitätsanzeige vorhanden',hasattr(self,'quality_class_var')))
            from .kit_inversion import extract_kit_temperature_profiles
            fixture_source={
                'id':'test-temp',
                'data':{
                    'variable':['PT_T_AIR_002_AVG','PT_T_AIR_010_AVG','PT_T_AIR_030_AVG','PT_T_AIR_060_AVG','PT_T_AIR_100_AVG','PT_T_AIR_130_AVG','PT_T_AIR_160_AVG','PT_T_AIR_200_AVG'],
                    'altitude':[2,10,30,60,100,130,160,200],
                    'value':[16.76,17.96,18.44,18.63,18.68,18.52,18.40,18.11],
                    'localtime':[1787617800000.0]*8,
                    'localtime_iso':['2026-08-25T00:30:00+02:00']*8,
                }
            }
            kit_test,_=extract_kit_temperature_profiles([fixture_source],datetime(2026,8,25).date())
            checks.append(('KIT-Temperaturprofil erkannt',kit_test is not None and len(kit_test)==1))
            checks.append(('KIT-Datumsfilter',kit_test.iloc[0]['time'].date()==datetime(2026,8,25).date()))
            checks.append(('KIT-Inversionsindex endlich',np.isfinite(kit_test.iloc[0]['kit_mast_index'])))
            from .archive import day_dir, source_ok
            checks.append(('Archivpfad ortsgetrennt', LOCATION_NAME.replace(' ','_')[:3].lower() in str(day_dir(datetime(2026,8,25).date())).lower() or bool(str(day_dir(datetime(2026,8,25).date())))))
            from .models import SourceStatus
            checks.append(('Archiv-Status ICON-D2 OK',source_ok('icon_d2',SourceStatus(name='x',state='OK'))))
            checks.append(('Archiv-Status KIT_TEMP_OK',source_ok('kit_mast',SourceStatus(name='x',state='KIT_TEMP_OK'))))
        except Exception: LOGGER.exception('Selbsttest intern fehlgeschlagen'); checks.append(('Interner Selbsttest',False))
        passed=sum(1 for _,ok in checks if ok); lines=[f"{'PASS' if ok else 'FAIL'} – {n}" for n,ok in checks]+['',f'Ergebnis: {passed}/{len(checks)} PASS']; self.log(f'Selbsttest: {passed}/{len(checks)} PASS'); (messagebox.showinfo if passed==len(checks) else messagebox.showwarning)('Selbsttest','\n'.join(lines),parent=self)
    def show_radiosonde_details(self):
        win=tk.Toplevel(self)
        win.title("Radiosonde Idar-Oberstein 10618 / DWD 02385 – Messprofile")
        win.geometry("900x560")

        frame=ttk.Frame(win,padding=10)
        frame.pack(fill="both",expand=True)

        status=None
        metrics=None
        if self.bundle:
            status=self.bundle.source_status.get("sonde")
            metrics=getattr(self.bundle,"sonde_metrics",None)

        header=self._status_text(status) if status else "Noch keine Radiosondendaten geladen"
        ttk.Label(frame,text=header,wraplength=860,justify="left").pack(anchor="w",pady=(0,10))

        columns=("time","index","grad","dt","depth","base","top","points")
        tree=ttk.Treeview(frame,columns=columns,show="headings",height=12)
        specs=[
            ("time","Start",110),
            ("index","Index",70),
            ("grad","max K/100m",100),
            ("dt","ΔT [K]",80),
            ("depth","Tiefe [m]",85),
            ("base","Basis [m]",85),
            ("top","Obergr. [m]",90),
            ("points","Rohpunkte",80),
        ]
        for key,title,width in specs:
            tree.heading(key,text=title)
            tree.column(key,width=width,anchor="center")

        if metrics is not None and not metrics.empty:
            for _,r in metrics.iterrows():
                tree.insert("", "end", values=(
                    f"{r['time']:%H:%M}",
                    f"{r['radiosonde_index']:.2f}",
                    f"{r['radiosonde_max_positive_gradient_K_per_100m']:.2f}",
                    f"{r['radiosonde_inversion_deltaT_K']:.2f}",
                    f"{r['radiosonde_inversion_depth_m']:.0f}",
                    f"{r['radiosonde_inversion_base_m']:.0f}",
                    f"{r['radiosonde_inversion_top_m']:.0f}",
                    int(r['radiosonde_profile_points']),
                ))
        tree.pack(fill="both",expand=True)

        note=(
            "Gemessene DWD-Radiosonde Idar-Oberstein. Die Temperaturprofile werden "
            "bis 2500 m über Startniveau ausgewertet, in 25-m-Höhenklassen verdichtet "
            "und leicht median-geglättet. Der daraus berechnete 0–5-Index ist eine "
            "separate räumliche Referenz und wird nicht mit dem Standortmodell "
            "oder ICON-D2 gemittelt."
        )
        ttk.Label(frame,text=note,wraplength=860,justify="left").pack(anchor="w",pady=(10,0))

    def show_kit_mast_details(self):
        win=tk.Toplevel(self)
        win.title("KIT 200-m-Meteomast – Details")
        win.geometry("860x620")

        outer=ttk.Frame(win,padding=10)
        outer.pack(fill="both",expand=True)

        status=None
        info={}
        if self.bundle:
            status=self.bundle.source_status.get("kit_mast")
            info=getattr(self.bundle,"kit_mast_info",{}) or {}

        ttk.Label(
            outer,
            text=self._status_text(status) if status else "Noch keine KIT-Mast-Diagnose geladen",
            wraplength=820,
            justify="left",
        ).pack(anchor="w",pady=(0,10))

        station_box=ttk.LabelFrame(outer,text="Station",padding=8)
        station_box.pack(fill="x",pady=(0,8))

        heights=info.get("temperature_heights_m",[2,10,30,60,100,130,160,200])
        distance=info.get("distance_to_viernheim_km")
        dist_text=f"{distance:.1f} km" if isinstance(distance,(int,float)) else "–"
        version=info.get("dashboard_version") or {}
        version_text=version.get("version","–") if isinstance(version,dict) else "–"
        version_date=version.get("date") if isinstance(version,dict) else None

        bokeh=info.get("bokeh",{}) or {}
        cds_count=len(info.get("bokeh_column_sources",[]) or [])
        payload_count=sum(
            page.get("parsed_payload_count",0)
            for page in bokeh.values()
            if isinstance(page,dict)
        )
        client=info.get("bokeh_client",{}) or {}
        client_sources=client.get("sources",[]) or []
        lines=[
            "Standort: KIT Campus Nord, 200-m-Meteomast",
            f"Entfernung zum aktiven Standort: {dist_text}",
            f"Temperatur-Messhöhen: {', '.join(str(x) for x in heights)} m",
            f"Dashboard-Version erkannt: v{version_text}" + (f" ({version_date})" if version_date else ""),
            f"Bokeh-JSON-Payloads: {payload_count}",
            f"ColumnDataSource-Kandidaten im HTML: {cds_count}",
            f"ColumnDataSource über Bokeh-Client: {len(client_sources)}",
            f"Bokeh-Client-Status: {client.get('state','–')}",
            f"Bokeh-Rohdaten JSON: {client.get('json_file') or '–'}",
            f"Bokeh-CSV-Dateien: {len(client.get('csv_files',[]) or [])}",
            "KIT-Zeit: localtime = lokale Europe/Berlin-Wandzeit (nicht UTC-konvertieren)",
            f"Diagnosedatei: {info.get('diagnostic_file') or '–'}",
            f"HTML-Snapshots: {info.get('html_snapshots') or {}}",
            "Für Gesamtindex verwendet: NEIN – gemessener KIT-Index wird separat dargestellt",
        ]
        ttk.Label(station_box,text="\n".join(lines),justify="left").pack(anchor="w")

        discovery=ttk.LabelFrame(outer,text="Numerische Schnittstellen-Diagnose",padding=8)
        discovery.pack(fill="both",expand=True,pady=(0,8))

        tree=ttk.Treeview(discovery,columns=("type","url"),show="headings",height=8)
        tree.heading("type",text="Typ")
        tree.heading("url",text="Gefundener Endpunkt")
        tree.column("type",width=90,anchor="center")
        tree.column("url",width=690,anchor="w")

        candidates=client_sources or info.get("best_bokeh_candidates",[]) or []
        for c in candidates[:20]:
            typ=f"CLIENT {c.get('heuristic_score',0)}" if client_sources else f"HTML {c.get('heuristic_score',0)}"
            cols=c.get('columns') if client_sources else c.get('column_names',[])
            desc=(
                f"id={c.get('id','–')} | "
                f"Zeilen≈{c.get('row_count_estimate',0)} | "
                f"Spalten={', '.join((cols or [])[:12])}"
            )
            tree.insert("", "end", values=(typ,desc))
        if not candidates:
            tree.insert("", "end", values=("–","Keine ColumnDataSource gefunden"))
        tree.pack(fill="both",expand=True)

        note=(
            "v0.8 arbeitet bewusst konservativ: Das öffentliche Dashboard wird überwacht, "
            "Diagrammbilder werden aber nicht per OCR in Messwerte umgewandelt. Erst wenn eine "
            "stabile numerische Schnittstelle und ihr Schema validiert sind, dürfen die "
            "2/10/30/60/100/130/160/200-m-Temperaturen den Index beeinflussen.\n\n"
            "KIT weist darauf hin, dass die Mastdaten nicht ohne Weiteres mit "
            "Bodenmessnetzdaten vergleichbar sind und wissenschaftliche bzw. kommerzielle "
            "Nutzung eine Einwilligung des Instituts erfordert."
        )
        ttk.Label(outer,text=note,wraplength=820,justify="left").pack(anchor="w")

    def on_close(self):
        self.save_settings()
        self.destroy()
