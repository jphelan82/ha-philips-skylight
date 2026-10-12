# Decode Bluetooth Mesh network PDUs (AD type 0x2A) from mesh.log with a known NetKey.
import sys,re
from cryptography.hazmat.primitives.cmac import CMAC
from cryptography.hazmat.primitives.ciphers import algorithms, Cipher, modes
from cryptography.hazmat.primitives.ciphers.aead import AESCCM
def cmac(k,m): c=CMAC(algorithms.AES(k)); c.update(m); return c.finalize()
def s1(m): return cmac(bytes(16),m)
def aes(k,b): e=Cipher(algorithms.AES(k),modes.ECB()).encryptor(); return e.update(b)+e.finalize()
def k2(n,p):
    t=cmac(s1(b'smk2'),n); t1=cmac(t,p+b'\x01'); t2=cmac(t,t1+p+b'\x02'); t3=cmac(t,t2+p+b'\x03')
    return t1[-1]&0x7f, t2, t3
def k4(a): t=cmac(s1(b'smk4'),a); return cmac(t,b'id6'+b'\x01')[-1]&0x3f
NET=bytes.fromhex(sys.argv[1]) if len(sys.argv)>1 else b'\x11'*16
IV=0
nid,ek,pk=k2(NET,b'\x00')
print(f"NetKey {NET.hex()} -> NID {nid:#04x}")
for line in open(sys.argv[2] if len(sys.argv)>2 else 'mesh2.log'):
    m=re.search(r'^(\S+) (\S+) .*raw=(\w+)',line)
    raw=bytes.fromhex(m.group(3))
    if len(raw)<2 or raw[1]!=0x2a:
        print(m.group(1), m.group(2)[:8], 'OTHER', raw.hex()); continue
    pdu=raw[2:2+raw[0]-1]
    ivi,pnid=pdu[0]>>7,pdu[0]&0x7f
    if pnid!=nid: print(m.group(1),'NID mismatch',hex(pnid)); continue
    obf=pdu[1:7]; enc=pdu[7:]
    pecb=aes(pk,bytes(5)+IV.to_bytes(4,'big')+enc[:7])
    hdr=bytes(a^b for a,b in zip(obf,pecb[:6]))
    ctl=hdr[0]>>7; ttl=hdr[0]&0x7f; seq=int.from_bytes(hdr[1:4],'big'); src=int.from_bytes(hdr[4:6],'big')
    nonce=b'\x00'+hdr+b'\x00\x00'+IV.to_bytes(4,'big')
    try: dec=AESCCM(ek,tag_length=8 if ctl else 4).decrypt(nonce,enc,None)
    except Exception: print(m.group(1),'NetMIC FAIL'); continue
    dst=int.from_bytes(dec[:2],'big'); tp=dec[2:]
    seg=tp[0]>>7; akf=(tp[0]>>6)&1; aid=tp[0]&0x3f
    acc=''
    if not ctl and not seg and akf:
        n=b'\x01\x00'+hdr[1:6]+dec[:2]+IV.to_bytes(4,'big')
        try: acc='ACCESS '+AESCCM(bytes(16),tag_length=4).decrypt(n,tp[1:],None).hex()
        except Exception: acc='appkey0 FAIL'
    print(f"{m.group(1)} {m.group(2)[:8]} ctl={ctl} ttl={ttl} seq={seq} src={src:#06x} dst={dst:#06x} seg={seg} akf={akf} aid={aid:#04x} {acc or 'upper='+tp[1:].hex()}")
