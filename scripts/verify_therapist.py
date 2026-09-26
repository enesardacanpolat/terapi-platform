"""Operator-only local command; use after manually reviewing credentials."""
import argparse
from pathlib import Path
import sys
import uuid
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import select
from app.db import SessionLocal
from app.models import TherapistProfile, User

parser=argparse.ArgumentParser(description='Belgelerini incelediğiniz uzman profilini onaylayın veya onayı kaldırın.')
parser.add_argument('profile_id',type=uuid.UUID)
parser.add_argument('--credentials-reviewed',action='store_true',help='Eğitim ve mesleki belgelerin manuel incelemesi tamamlandı.')
parser.add_argument('--revoke',action='store_true',help='Profilin doğrulamasını kaldır.')
args=parser.parse_args()
if not args.revoke and not args.credentials_reviewed:
    parser.error('Onaylamak için belgeleri inceleyip --credentials-reviewed kullanın.')
with SessionLocal() as db:
    profile=db.scalar(select(TherapistProfile).where(TherapistProfile.id==args.profile_id).with_for_update())
    if not profile:parser.error('Profil bulunamadı.')
    profile.is_verified=not args.revoke
    db.commit()
    print(f'{db.get(User,profile.user_id).full_name}: '+('doğrulama kaldırıldı' if args.revoke else 'doğrulandı'))
