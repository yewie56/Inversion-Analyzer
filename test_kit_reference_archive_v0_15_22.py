# -*- coding: utf-8 -*-
from datetime import date
from pathlib import Path
import tempfile
import pandas as pd

from inversion import kit_reference_archive as kra
from inversion import archive as arc
from inversion.models import DataBundle


def check(name, cond, detail=''):
    if not cond:
        raise AssertionError(f'FAIL | {name} | {detail}')
    print(f'PASS | {name}')


def main():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)/'archive'
        kra.ARCHIVE_DIR=root
        d=date(2026,8,30)
        check('globaler KIT-Pfad', kra.kit_reference_day_dir(d)==root/'KITMast'/'2026'/'08'/'30')
        a=pd.DataFrame({'time':['2026-08-30T10:00:00+02:00','2026-08-30T11:00:00+02:00'],'kit_mast_index':[1.0,2.0]})
        b=pd.DataFrame({'time':['2026-08-30T11:00:00+02:00','2026-08-30T12:00:00+02:00'],'kit_mast_index':[2.5,3.0]})
        kra.save_kit_reference(d,a,info={'a':1},status_state='KIT_TEMP_OK',source='TEST_A')
        kra.save_kit_reference(d,b,info={'b':2},status_state='KIT_TEMP_OK',source='TEST_B')
        df,info,status,manifest=kra.load_kit_reference(d)
        check('Safe-Merge behält 3 Zeitpunkte', len(df)==3, str(df))
        row=df[pd.to_datetime(df['time'],utc=True)==pd.Timestamp('2026-08-30T09:00:00Z')]
        check('neuer Duplikatwert gewinnt', abs(float(row.iloc[0]['kit_mast_index'])-2.5)<1e-9)
        check('globales Manifest', manifest.get('archive_kind')=='KITMast')

        legacy=root/'Viernheim'/'2026'/'08'/'29'
        legacy.mkdir(parents=True)
        pd.DataFrame({'time':['2026-08-29T22:00:00+02:00'],'kit_mast_index':[4.0]}).to_csv(legacy/'kit_mast.csv',index=False)
        migrated=kra.migrate_legacy_kit_archives()
        df2,_,_,_=kra.load_kit_reference(date(2026,8,29))
        check('Legacy-KIT migriert', migrated>=1 and df2 is not None and len(df2)==1)

        # Location archives must consume the global reference without writing duplicates.
        arc.ARCHIVE_DIR=root
        loc_day=date(2026,8,30)
        bundle=DataBundle(run_id='test')
        arc.save_bundle(loc_day,bundle,{'reason':'TEST','increment_attempt':False,'affects_retry_clock':False},touched_sources={'kit_mast'})
        local=arc.day_dir(loc_day)
        check('kein lokales KIT-CSV dupliziert', not (local/'kit_mast.csv').exists())
        local_manifest=__import__('json').loads((local/'manifest.json').read_text(encoding='utf-8'))
        check('Manifest referenziert globales KIT', local_manifest.get('kit_reference',{}).get('enabled') is True)
        check('kein lokaler KIT-Dateiverweis', 'kit_mast_metrics' not in local_manifest.get('files',{}))
        loaded,_=arc.load_bundle(loc_day)
        check('Location lädt globales KIT transparent', loaded is not None and loaded.kit_mast_metrics is not None and len(loaded.kit_mast_metrics)==3)
    print('PASS | v0.15.22 central KIT archive regression complete')
    return 0

if __name__=='__main__':
    raise SystemExit(main())
