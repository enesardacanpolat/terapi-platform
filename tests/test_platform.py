"""End-to-end API checks against an isolated PostgreSQL schema; no existing data changed."""
import concurrent.futures
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.config import settings


class PlatformTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = 'iyi_test_' + uuid.uuid4().hex
        cls.admin = create_engine(settings.database_url, echo=False)
        with cls.admin.begin() as c:
            cls.original_user_count = c.execute(text('SELECT count(*) FROM public.users')).scalar()
            c.execute(text(f'CREATE SCHEMA {cls.schema}'))
        cls.url = make_url(settings.database_url).update_query_dict({'options': f'-csearch_path={cls.schema},public'}).render_as_string(hide_password=False)
        cls.env = {**os.environ, 'DATABASE_URL': cls.url, 'DEBUG': 'false'}
        cls.db = create_engine(cls.url)
        try:
            subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', 'head'], env=cls.env, cwd=ROOT, check=True, capture_output=True)
            with cls.db.connect() as c:
                assert c.execute(text(f'SELECT count(*) FROM {cls.schema}.users')).scalar() == 0
                assert c.execute(text(f'SELECT version_num FROM {cls.schema}.alembic_version')).scalar() == 'b17c20260923'
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
            cls.base = f'http://127.0.0.1:{port}'
            cls.log = tempfile.TemporaryFile()
            cls.server = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', str(port)], env=cls.env, cwd=ROOT, stdout=cls.log, stderr=cls.log)
            for _ in range(60):
                try:
                    urllib.request.urlopen(cls.base+'/health', timeout=1).close(); break
                except OSError:
                    time.sleep(.1)
            else:
                cls.log.seek(0); raise RuntimeError(cls.log.read().decode())
        except BaseException:
            cls.tearDownClass(); raise

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, 'server'):
            cls.server.terminate(); cls.server.wait(timeout=10); cls.log.close()
        cls.db.dispose()
        with cls.admin.begin() as c:
            c.execute(text(f'DROP SCHEMA {cls.schema} CASCADE'))
            assert c.execute(text('SELECT count(*) FROM public.users')).scalar() == cls.original_user_count, 'Public data changed during tests'
        cls.admin.dispose()

    def request(self, path, data=None, token=None, method=None):
        req = urllib.request.Request(self.base+path, data=json.dumps(data).encode() if data is not None else None,
                                     headers={'Content-Type':'application/json', **({'Authorization':'Bearer '+token} if token else {})}, method=method)
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                content = r.read(); return r.status, json.loads(content) if content else None
        except urllib.error.HTTPError as e:
            return e.code, json.load(e)

    def user(self, role='client'):
        email=f'{uuid.uuid4().hex}@example.com'; password='TestOnly2026!'
        code,user=self.request('/register',{'email':email,'password':password,'full_name':'Test Kullanıcı','role':role}); self.assertEqual(code,201)
        code,token=self.request('/login',{'email':email,'password':password}); self.assertEqual(code,200)
        return user,token['access_token']

    def setUp(self):
        self.client,self.ct=self.user()
        self.therapist,self.tt=self.user('therapist')
        self.profile_payload={'title':'Psikolog','license_no':'TEST123','bio':'Test profili','education':['Test Üniversitesi'],'session_minutes':50,'session_price':1000,'specialties':['Kaygı ve stres','Kendini tanıma']}
        code,self.p=self.request('/api/therapists/me',self.profile_payload,self.tt,'PUT');self.assertEqual(code,200)
        with self.db.begin() as c:
            c.execute(text('UPDATE therapist_profiles SET is_verified=true WHERE id=:id'),{'id':self.p['id']})
        self.day=(datetime.now(ZoneInfo('Europe/Istanbul'))+timedelta(days=2)).date()
        code,_=self.request('/api/therapists/me/availability',{'weekday':self.day.weekday(),'start_time':'09:00','end_time':'18:00'},self.tt);self.assertEqual(code,201)
        self.booking={'therapist_id':self.p['id'],'date':str(self.day),'start_time':'09:00'}

    def test_booking_ownership_cancel_and_slot_release(self):
        code,slots=self.request(f"/api/therapists/{self.p['id']}/slots?date={self.day}");self.assertEqual(code,200);self.assertEqual(len(slots['slots']),10)
        payload={**self.booking,'mood':'kaygili','expectations':['Kaygı ve stres']}
        code,a=self.request('/api/appointments',payload,self.ct);self.assertEqual(code,201);self.assertEqual(a['session_price'],1000)
        self.assertEqual(self.request('/api/appointments',self.booking,self.ct)[0],409)
        code,listed=self.request('/api/appointments',token=self.tt);self.assertEqual(listed[0]['mood'],'kaygili')
        _,other=self.user();self.assertEqual(self.request('/api/appointments/'+a['id'],{'status':'cancelled'},other,'PATCH')[0],404)
        self.assertEqual(self.request('/api/appointments/'+a['id'],{'status':'confirmed'},self.ct,'PATCH')[0],409)
        self.assertEqual(self.request('/api/appointments/'+a['id'],{'status':'confirmed'},self.tt,'PATCH')[0],200)
        self.assertEqual(self.request('/api/appointments/'+a['id'],{'status':'completed'},self.tt,'PATCH')[0],409)
        self.assertEqual(self.request('/api/appointments/'+a['id'],{'status':'cancelled'},self.ct,'PATCH')[0],200)
        self.assertEqual(self.request('/api/appointments',self.booking,self.ct)[0],201)

    def test_two_simultaneous_bookings_only_one_succeeds(self):
        _,other=self.user()
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            codes=list(pool.map(lambda t:self.request('/api/appointments',self.booking,t)[0],[self.ct,other]))
        self.assertEqual(sorted(codes),[201,409])

    def test_client_cannot_book_two_therapists_at_same_time(self):
        _,second=self.user('therapist');_,p=self.request('/api/therapists/me',self.profile_payload,second,'PUT')
        with self.db.begin() as c:c.execute(text('UPDATE therapist_profiles SET is_verified=true WHERE id=:id'),{'id':p['id']})
        self.request('/api/therapists/me/availability',{'weekday':self.day.weekday(),'start_time':'09:00','end_time':'18:00'},second)
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            codes=list(pool.map(lambda pid:self.request('/api/appointments',{**self.booking,'therapist_id':pid},self.ct)[0],[self.p['id'],p['id']]))
        self.assertEqual(sorted(codes),[201,409])

    def test_time_validation_and_roles(self):
        for bad in ['oops','09:00:30','09:00+03:00']:
            self.assertEqual(self.request('/api/appointments',{**self.booking,'start_time':bad},self.ct)[0],422)
        for value in ['09:01','08:00','18:00']:
            self.assertEqual(self.request('/api/appointments',{**self.booking,'start_time':value},self.ct)[0],409)
        self.assertEqual(self.request('/api/appointments',{**self.booking,'date':str(self.day-timedelta(days=5))},self.ct)[0],409)
        self.assertEqual(self.request('/api/appointments',self.booking,self.tt)[0],403)
        self.assertEqual(self.request('/api/therapists/me',self.profile_payload,self.ct,'PUT')[0],403)
        self.assertEqual(self.request('/api/therapists/me/availability',{'weekday':0,'start_time':'18:00','end_time':'09:00'},self.tt)[0],422)
        self.assertEqual(self.request('/api/therapists/me/availability',{'weekday':self.day.weekday(),'start_time':'10:00','end_time':'12:00'},self.tt)[0],409)

    def test_verification_private_fields_and_matching(self):
        code,p=self.request('/api/therapists/'+self.p['id']);self.assertEqual(code,200);self.assertNotIn('license_no',p)
        code,data=self.request('/api/therapists?mood=kaygili');self.assertTrue(any(p['id']==self.p['id'] and 'Kaygı ve stres' in p['match_reasons'] for p in data))
        payload={**self.profile_payload,'education':['Yeni üniversite']}
        self.assertEqual(self.request('/api/therapists/me',payload,self.tt,'PUT')[0],200)
        self.assertEqual(self.request('/api/therapists/'+self.p['id'])[0],404)
        self.assertEqual(self.request('/api/appointments',self.booking,self.ct)[0],404)

    def test_completed_session_review_once_anonymized(self):
        review={'therapist_id':self.p['id'],'rating':5,'comment':'Güzel bir deneyimdi.'}
        self.assertEqual(self.request('/api/reviews',review,self.ct)[0],403)
        _,a=self.request('/api/appointments',self.booking,self.ct)
        with self.db.begin() as c:
            c.execute(text("UPDATE appointments SET status='confirmed',slot=tstzrange(now()-interval '2 hours',now()-interval '1 hour','[)') WHERE id=:id"),{'id':a['id']})
        self.assertEqual(self.request('/api/appointments/'+a['id'],{'status':'completed'},self.tt,'PATCH')[0],200)
        self.assertEqual(self.request('/api/reviews',review,self.ct)[0],201)
        self.assertEqual(self.request('/api/reviews',review,self.ct)[0],409)
        _,reviews=self.request('/api/therapists/'+self.p['id']+'/reviews');self.assertEqual(len(reviews),1);self.assertNotIn('client_id',reviews[0])
        _,p=self.request('/api/therapists/'+self.p['id']);self.assertEqual(p['rating'],5)

    def test_time_off_and_no_intake_by_default(self):
        start=datetime.combine(self.day,datetime.min.time(),ZoneInfo('Europe/Istanbul'))+timedelta(hours=9)
        with self.db.begin() as c:
            c.execute(text('INSERT INTO time_offs (id,therapist_id,starts_at,ends_at) VALUES (:id,:pid,:start,:end)'),{'id':uuid.uuid4(),'pid':self.p['id'],'start':start,'end':start+timedelta(minutes=50)})
        self.assertEqual(self.request('/api/appointments',self.booking,self.ct)[0],409)
        code,a=self.request('/api/appointments',{**self.booking,'start_time':'09:50'},self.ct);self.assertEqual(code,201);self.assertIsNone(a['mood']);self.assertEqual(a['expectations'],[])

    def test_database_constraint_blocks_direct_overlap(self):
        _,a=self.request('/api/appointments',self.booking,self.ct)
        from sqlalchemy.exc import IntegrityError
        with self.assertRaises(IntegrityError):
            with self.db.begin() as c:
                c.execute(text("INSERT INTO appointments(id,therapist_id,client_id,slot,status,expectations) SELECT :id,therapist_id,client_id,slot,'pending','[]' FROM appointments WHERE id=:existing"),{'id':uuid.uuid4(),'existing':a['id']})

    def test_auth_rejects_admin_and_invalid_subject(self):
        from app.security import create_access_token
        self.assertEqual(self.request('/me',token=create_access_token('not-a-uuid'))[0],401)
        self.assertEqual(self.request('/register',{'email':'admin@example.com','password':'TestOnly2026!','full_name':'Admin Test','role':'admin'})[0],422)
        self.assertEqual(self.request('/api/appointments')[0],401)


if __name__ == '__main__':
    unittest.main(verbosity=2)
