"""Run an explicitly labelled, disposable local demo without modifying real records."""
import os
from pathlib import Path
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
from app.config import settings
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

schema = 'iyi_demo_' + uuid.uuid4().hex
admin = create_engine(settings.database_url, echo=False)
with admin.begin() as c:
    c.execute(text(f'CREATE SCHEMA {schema}'))
url = make_url(settings.database_url).update_query_dict({'options': f'-csearch_path={schema},public'}).render_as_string(hide_password=False)
env = {**os.environ, 'DATABASE_URL': url, 'DEBUG': 'false', 'DEMO_MODE': 'true'}
demo = None
try:
    subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', 'head'], env=env, cwd=ROOT, check=True)
    settings.database_url = url
    settings.debug = False
    from app import models as m
    from app.security import hash_password
    demo = create_engine(url)
    with demo.connect() as c:
        assert c.execute(text(f'SELECT count(*) FROM {schema}.users')).scalar() == 0
    with Session(demo) as db:
        client = m.User(email='danisan@iyi.example', full_name='Demo Danışan', password_hash=hash_password('IyiDemo2026!'), role='client')
        db.add(client)
        samples = [
            ('Deniz Yılmaz', 'Psikolog', ['Kaygı ve stres', 'Kendini tanıma', 'Özgüven'], 1250, 'Kendini anlamaya ve duygularına yer açmaya birlikte başlayabiliriz. Her insanın kendine özgü bir yolculuğu olduğuna inanıyorum.'),
            ('Ece Demir', 'Psikolojik danışman', ['İlişkiler', 'Duygusal zorluklar', 'Kendini tanıma'], 1100, 'İlişkilerinde ve günlük yaşamında sana iyi gelen yolları keşfetmen için yanında olmayı önemsiyorum.'),
            ('Can Aydın', 'Psikolog', ['Kaygı ve stres', 'İş ve yaşam dengesi', 'Özgüven'], 1400, 'Hayatın temposunda kendine alan açmak mümkün. İhtiyaçlarını fark etmene ve kendi ritmini bulmana eşlik ediyorum.'),
        ]
        for i,(name,title,areas,price,bio) in enumerate(samples):
            user=m.User(email=f'uzman{i+1}@iyi.example',full_name=name,password_hash=hash_password('IyiDemo2026!'),role='therapist')
            db.add(user);db.flush()
            profile=m.TherapistProfile(user_id=user.id,title=title,bio=bio,license_no=f'ORNEK-{i+1}',is_verified=True,education=['Örnek Üniversite · '+('Psikoloji' if title=='Psikolog' else 'Psikolojik Danışmanlık')+' Lisans', 'Bu profil ve eğitim bilgileri tanıtım amaçlıdır.'],session_minutes=50,session_price=price)
            db.add(profile);db.flush()
            for name in areas:
                from sqlalchemy import select
                specialty=db.scalar(select(m.Specialty).where(m.Specialty.name==name))
                if not specialty:
                    specialty=m.Specialty(name=name);db.add(specialty);db.flush()
                db.execute(m.Specialty.therapist_specialties.insert().values(therapist_id=profile.id,specialty_id=specialty.id))
            for day in range(7):
                from datetime import time
                db.add(m.AvailabilityRule(therapist_id=profile.id,weekday=day,start_time=time(9),end_time=time(18)))
        db.commit()
    print('\nDemo: http://127.0.0.1:8000\nDanışan: danisan@iyi.example\nUzman: uzman1@iyi.example\nŞifre (tüm örnek hesaplar): IyiDemo2026!\nBu oturumdaki veriler demo kapanınca silinir.\n', flush=True)
    server=subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000'],env=env,cwd=ROOT)
    try:
        server.wait()
    except KeyboardInterrupt:
        server.terminate();server.wait(timeout=10)
finally:
    if demo:demo.dispose()
    with admin.begin() as c:
        c.execute(text(f'DROP SCHEMA {schema} CASCADE'))
    admin.dispose()
