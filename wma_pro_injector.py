"""
Native Windows WMA Pro Audio Injector for Just Dance Greatest Hits (Xbox 360)
Preserves 100% bit-for-bit video payloads, headers, timestamps, and ASF packet structure.
Uses Microsoft's built-in WMAudio Encoder DMO via COM (ctypes) to produce exact WMA Pro CBR blocks.
"""

import os
import sys
import struct
import ctypes
import uuid

ole32 = ctypes.windll.ole32
ole32.CoInitialize(None)

class GUID(ctypes.Structure):
    _fields_ = [
        ('Data1', ctypes.c_ulong),
        ('Data2', ctypes.c_ushort),
        ('Data3', ctypes.c_ushort),
        ('Data4', ctypes.c_ubyte * 8)
    ]
    def __init__(self, u):
        u_obj = uuid.UUID(u)
        super().__init__()
        self.Data1 = u_obj.time_low
        self.Data2 = u_obj.time_mid
        self.Data3 = u_obj.time_hi_version
        for i, b in enumerate(u_obj.bytes[8:]):
            self.Data4[i] = b

class IMediaBufferVtbl(ctypes.Structure):
    _fields_ = [
        ('QueryInterface', ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p))),
        ('AddRef', ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)),
        ('Release', ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)),
        ('SetLength', ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_ulong)),
        ('GetMaxLength', ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong))),
        ('GetBufferAndLength', ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_ulong))),
    ]

class COMObject(ctypes.Structure):
    _fields_ = [('lpVtbl', ctypes.POINTER(IMediaBufferVtbl))]

_alive_buffers = []

class PyMediaBuffer:
    def __init__(self, max_len):
        self.max_len = max_len
        self.cur_len = 0
        self.raw_buf = (ctypes.c_ubyte * max_len)()
        self.ref_count = 1
        
        def QI(this, riid, ppv):
            ppv[0] = ctypes.addressof(self.com_obj)
            self.ref_count += 1
            return 0
        def AddRef(this):
            self.ref_count += 1
            return self.ref_count
        def Release(this):
            self.ref_count -= 1
            return self.ref_count
        def SetLength(this, cb):
            if cb > self.max_len: return -2147024809
            self.cur_len = cb
            return 0
        def GetMaxLength(this, pcb):
            pcb[0] = self.max_len
            return 0
        def GetBufferAndLength(this, ppb, pcb):
            if ppb: ppb[0] = ctypes.cast(self.raw_buf, ctypes.c_void_p).value
            if pcb: pcb[0] = self.cur_len
            return 0

        self.vtbl = IMediaBufferVtbl(
            ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p))(QI),
            ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(AddRef),
            ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(Release),
            ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_ulong)(SetLength),
            ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong))(GetMaxLength),
            ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_ulong))(GetBufferAndLength)
        )
        self.com_obj = COMObject(ctypes.pointer(self.vtbl))
        self.p_interface = ctypes.addressof(self.com_obj)
        _alive_buffers.append(self)

class DMO_MEDIA_TYPE(ctypes.Structure):
    _fields_ = [
        ('majortype', GUID),
        ('subtype', GUID),
        ('bFixedSizeSamples', ctypes.c_int),
        ('bTemporalCompression', ctypes.c_int),
        ('lSampleSize', ctypes.c_ulong),
        ('formattype', GUID),
        ('pUnk', ctypes.c_void_p),
        ('cbFormat', ctypes.c_ulong),
        ('pbFormat', ctypes.POINTER(ctypes.c_ubyte))
    ]

class DMO_OUTPUT_DATA_BUFFER(ctypes.Structure):
    _fields_ = [
        ('pBuffer', ctypes.c_void_p),
        ('dwStatus', ctypes.c_ulong),
        ('rtTimestamp', ctypes.c_int64),
        ('rtTimelength', ctypes.c_int64)
    ]

class IMediaObjectVtbl(ctypes.Structure):
    _fields_ = [
        ('QueryInterface', ctypes.c_void_p),
        ('AddRef', ctypes.c_void_p),
        ('Release', ctypes.c_void_p),
        ('GetStreamCount', ctypes.c_void_p),
        ('GetInputStreamInfo', ctypes.c_void_p),
        ('GetOutputStreamInfo', ctypes.c_void_p),
        ('GetInputType', ctypes.c_void_p),
        ('GetOutputType', ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.POINTER(DMO_MEDIA_TYPE))),
        ('SetInputType', ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(DMO_MEDIA_TYPE), ctypes.c_ulong)),
        ('SetOutputType', ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(DMO_MEDIA_TYPE), ctypes.c_ulong)),
        ('GetInputCurrentType', ctypes.c_void_p),
        ('GetOutputCurrentType', ctypes.c_void_p),
        ('GetInputSizeInfo', ctypes.c_void_p),
        ('GetOutputSizeInfo', ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_ulong))),
        ('GetInputMaxLatency', ctypes.c_void_p),
        ('SetInputMaxLatency', ctypes.c_void_p),
        ('Flush', ctypes.c_void_p),
        ('Discontinuity', ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_ulong)),
        ('AllocateStreamingResources', ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p)),
        ('FreeStreamingResources', ctypes.c_void_p),
        ('GetInputStatus', ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong))),
        ('ProcessInput', ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_ulong, ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int64, ctypes.c_int64)),
        ('ProcessOutput', ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.POINTER(DMO_OUTPUT_DATA_BUFFER), ctypes.POINTER(ctypes.c_ulong))),
    ]

def get_wmv_audio_info(wmv_path):
    """
    Parses an ASF/WMV file to extract header size, packet size, block align, total packet count,
    and total audio payload count.
    """
    def rd(b, o, t):
        if t == 0: return 0, 0
        if t == 1: return b[o], 1
        if t == 2: return struct.unpack('<H', b[o:o+2])[0], 2
        if t == 3: return struct.unpack('<I', b[o:o+4])[0], 4

    with open(wmv_path, 'rb') as f:
        head = f.read(30)
        hs = struct.unpack('<Q', head[16:24])[0]
        n = struct.unpack('<I', head[24:28])[0]
        f.seek(0)
        hdr = f.read(hs)
        p = 30
        psz = 8000
        block_align = 4096
        for _ in range(n):
            guid = hdr[p:p+16].hex().upper()
            sz = struct.unpack('<Q', hdr[p+16:p+24])[0]
            body = hdr[p+24:p+sz]
            if guid == 'A1DCAB8C47A9CF118EE400C00C205365':
                psz = struct.unpack('<I', body[68:72])[0]
            elif guid == '9107DCB7B7A9CF118EE600C00C205365':
                stream_type = body[:16].hex().upper()
                if stream_type.startswith('409E69F8'):
                    t_spec_len = struct.unpack('<I', body[40:44])[0]
                    spec = body[54:54+t_spec_len]
                    block_align = struct.unpack('<H', spec[12:14])[0]
            p += sz

        f.seek(hs)
        dhdr = f.read(50)
        tot_pkts = struct.unpack('<Q', dhdr[40:48])[0]

        audio_payload_count = 0
        for _ in range(tot_pkts):
            pkt = f.read(psz)
            o = 0
            ecf = pkt[0]
            if ecf & 0x80: o = 1 + (ecf & 0x0F)
            lt = pkt[o]; pt = pkt[o+1]; o += 2
            plen, k = rd(pkt, o, (lt>>5)&3); o += k
            seq, k = rd(pkt, o, (lt>>1)&3); o += k
            pad, k = rd(pkt, o, (lt>>3)&3); o += k
            send, dur = struct.unpack('<IH', pkt[o:o+6]); o += 6
            multi = lt & 1
            npl = (pkt[o] & 0x3F) if multi else 1
            plt = (pkt[o] >> 6) & 3 if multi else 0
            if multi: o += 1

            for j in range(npl):
                sn = pkt[o] & 0x7F; o += 1
                mon, k = rd(pkt, o, (pt>>4)&3); o += k
                off, k = rd(pkt, o, (pt>>2)&3); o += k
                rl, k = rd(pkt, o, pt&3); o += k
                rep = pkt[o:o+rl]; o += rl
                if multi: dl, k = rd(pkt, o, plt); o += k
                else: dl = psz - o - pad
                if sn == 1:
                    audio_payload_count += 1
                o += dl

    return hs, psz, block_align, tot_pkts, audio_payload_count

def encode_pcm_to_wmapro(pcm_data, block_align, target_blocks_count):
    """
    Encodes 16-bit 48kHz stereo PCM data into WMA Pro CBR blocks using Microsoft's native DMO.
    Automatically matches block_align (4096 or 8192 bytes).
    """
    CLSID_WMA = GUID('70f598e9-f4ab-495a-99e2-a7c4d3d89abf')
    IID_IMediaObject = GUID('d8ad0f58-5494-4102-97c5-ec798e59bcf4')

    pMediaObject = ctypes.c_void_p()
    hr = ole32.CoCreateInstance(ctypes.byref(CLSID_WMA), None, 1, ctypes.byref(IID_IMediaObject), ctypes.byref(pMediaObject))
    if hr != 0 or not pMediaObject.value:
        raise RuntimeError(f"Could not create the Windows WMAudio Encoder DMO (HRESULT 0x{hr & 0xFFFFFFFF:08X})")
    vtbl = ctypes.cast(ctypes.cast(pMediaObject.value, ctypes.POINTER(ctypes.c_void_p))[0], ctypes.POINTER(IMediaObjectVtbl)).contents

    # Find matching output type for block_align, 48000Hz, 2ch, 192k
    mt_out = DMO_MEDIA_TYPE()
    matched_type_idx = None
    for i in range(250):
        hr = vtbl.GetOutputType(pMediaObject.value, 0, i, ctypes.byref(mt_out))
        if hr != 0: break
        if mt_out.cbFormat >= 18:
            raw = bytes(mt_out.pbFormat[:mt_out.cbFormat])
            tag, ch, rate, br = struct.unpack('<HHIi', raw[:12])
            ba = struct.unpack('<H', raw[12:14])[0]
            bits = struct.unpack('<H', raw[14:16])[0]
            if tag == 0x162 and ch == 2 and rate == 48000 and (br * 8) == 192000 and ba == block_align and bits == 16:
                matched_type_idx = i
                break

    if matched_type_idx is None:
        matched_type_idx = 188 if block_align == 4096 else 109

    vtbl.GetOutputType(pMediaObject.value, 0, matched_type_idx, ctypes.byref(mt_out))
    vtbl.SetOutputType(pMediaObject.value, 0, ctypes.byref(mt_out), 0)

    # Set Input Type (PCM 48kHz 16-bit stereo)
    pcm_spec = struct.pack('<HHIIHHH', 1, 2, 48000, 48000*4, 4, 16, 0)
    buf_in = (ctypes.c_ubyte * len(pcm_spec)).from_buffer_copy(pcm_spec)

    mt_in = DMO_MEDIA_TYPE()
    mt_in.majortype = GUID('73647561-0000-0010-8000-00aa00389b71')
    mt_in.subtype = GUID('00000001-0000-0010-8000-00aa00389b71')
    mt_in.bFixedSizeSamples = 1
    mt_in.bTemporalCompression = 0
    mt_in.lSampleSize = 4
    mt_in.formattype = GUID('05589f81-c356-11ce-bf01-00aa0055595a')
    mt_in.cbFormat = len(pcm_spec)
    mt_in.pbFormat = buf_in
    vtbl.SetInputType(pMediaObject.value, 0, ctypes.byref(mt_in), 0)
    vtbl.AllocateStreamingResources(pMediaObject.value)

    out_buf = PyMediaBuffer(block_align)
    out_db = DMO_OUTPUT_DATA_BUFFER()
    out_db.pBuffer = out_buf.p_interface
    out_status = ctypes.c_ulong(0)

    chunk_samples = 2048 * 4  # 8192 samples (170.666 ms), aligned to WMA Pro frames
    chunk_size = chunk_samples * 4  # 16-bit stereo = 4 bytes per sample
    pos = 0
    total_pcm = len(pcm_data)
    encoded_blocks = []
    block_timestamps = []
    rt_time = 0

    while pos < total_pcm:
        chunk = pcm_data[pos : pos + chunk_size]
        pos += len(chunk)
        samples_in_chunk = len(chunk) // 4
        rt_dur = int((samples_in_chunk / 48000) * 10_000_000)

        in_buf = PyMediaBuffer(len(chunk))
        ctypes.memmove(in_buf.raw_buf, chunk, len(chunk))
        in_buf.cur_len = len(chunk)

        # Pass SYNCPOINT (0x01) | TIME (0x02) = 0x03 with continuous REFERENCE_TIME
        vtbl.ProcessInput(pMediaObject.value, 0, in_buf.p_interface, 3, rt_time, rt_dur)
        rt_time += rt_dur

        while True:
            out_buf.cur_len = 0
            hr = vtbl.ProcessOutput(pMediaObject.value, 0, 1, ctypes.byref(out_db), ctypes.byref(out_status))
            if out_buf.cur_len == block_align:
                encoded_blocks.append(bytes(out_buf.raw_buf[:block_align]))
                block_timestamps.append(out_db.rtTimestamp / 10000.0)
            if not (out_db.dwStatus & 1):
                break

    # If the replacement audio is shorter than the original track, keep feeding
    # silence until enough blocks exist (instead of repeating the last block).
    silence = bytes(chunk_size)
    guard = 0
    while len(encoded_blocks) < target_blocks_count and guard < 600:
        guard += 1
        in_buf = PyMediaBuffer(len(silence))
        in_buf.cur_len = len(silence)
        samples_in_chunk = len(silence) // 4
        rt_dur = int((samples_in_chunk / 48000) * 10_000_000)
        vtbl.ProcessInput(pMediaObject.value, 0, in_buf.p_interface, 3, rt_time, rt_dur)
        rt_time += rt_dur
        while True:
            out_buf.cur_len = 0
            hr = vtbl.ProcessOutput(pMediaObject.value, 0, 1, ctypes.byref(out_db), ctypes.byref(out_status))
            if out_buf.cur_len == block_align:
                encoded_blocks.append(bytes(out_buf.raw_buf[:block_align]))
                block_timestamps.append(out_db.rtTimestamp / 10000.0)
            if not (out_db.dwStatus & 1):
                break

    # Flush trailing blocks
    vtbl.Discontinuity(pMediaObject.value, 0)
    while len(encoded_blocks) < target_blocks_count:
        out_buf.cur_len = 0
        hr = vtbl.ProcessOutput(pMediaObject.value, 0, 1, ctypes.byref(out_db), ctypes.byref(out_status))
        if out_buf.cur_len == block_align:
            encoded_blocks.append(bytes(out_buf.raw_buf[:block_align]))
            block_timestamps.append(out_db.rtTimestamp / 10000.0)
        else:
            break

    # Match target block count
    if len(encoded_blocks) < target_blocks_count:
        raise RuntimeError(
            f"WMA Pro encoder produced {len(encoded_blocks)} blocks, expected {target_blocks_count}")
    elif len(encoded_blocks) > target_blocks_count:
        encoded_blocks = encoded_blocks[:target_blocks_count]
        block_timestamps = block_timestamps[:target_blocks_count]

    return encoded_blocks, block_timestamps

def inject_audio_into_wmv(orig_wmv_path, new_blocks, out_wmv_path, psz, block_align, tot_pkts, block_timestamps=None):
    """
    Copies the original WMV file byte-for-byte, swapping only the audio payloads.
    Preserves all headers, packet structures, video stream payloads, timestamps,
    replicated data extensions, and simple index.
    """
    def rd(b, o, t):
        if t == 0: return 0, 0
        if t == 1: return b[o], 1
        if t == 2: return struct.unpack('<H', b[o:o+2])[0], 2
        if t == 3: return struct.unpack('<I', b[o:o+4])[0], 4

    with open(orig_wmv_path, 'rb') as fin, open(out_wmv_path, 'wb') as fout:
        head = fin.read(30)
        hs = struct.unpack('<Q', head[16:24])[0]
        fin.seek(0)
        hdr_bytes = fin.read(hs)
        fout.write(hdr_bytes)

        data_hdr = fin.read(50)
        fout.write(data_hdr)

        block_idx = 0
        replaced_payloads = 0

        for p_i in range(tot_pkts):
            pkt = bytearray(fin.read(psz))
            o = 0
            ecf = pkt[0]
            if ecf & 0x80:
                o = 1 + (ecf & 0x0F)
            lt = pkt[o]
            pt = pkt[o+1]
            o += 2
            plen, k = rd(pkt, o, (lt>>5)&3); o += k
            seq, k = rd(pkt, o, (lt>>1)&3); o += k
            pad, k = rd(pkt, o, (lt>>3)&3); o += k
            send, dur = struct.unpack('<IH', pkt[o:o+6]); o += 6
            multi = lt & 1
            npl = (pkt[o] & 0x3F) if multi else 1
            plt = (pkt[o] >> 6) & 3 if multi else 0
            if multi: o += 1

            for j in range(npl):
                sn = pkt[o] & 0x7F; o += 1
                mon, k = rd(pkt, o, (pt>>4)&3); o += k
                off, k = rd(pkt, o, (pt>>2)&3); o += k
                rl, k = rd(pkt, o, pt&3); o += k
                rep_start = o
                rep = pkt[o:o+rl]; o += rl
                if multi: dl, k = rd(pkt, o, plt); o += k
                else: dl = psz - o - pad

                if sn == 1: # Audio stream
                    if dl == block_align and block_idx < len(new_blocks):
                        pkt[o : o + dl] = new_blocks[block_idx]
                        if rl >= 8 and block_timestamps is not None and block_idx < len(block_timestamps):
                            new_pts = 3000 + int(round(block_timestamps[block_idx]))
                            pkt[rep_start + 4 : rep_start + 8] = struct.pack('<I', new_pts)
                        block_idx += 1
                        replaced_payloads += 1

                o += dl

            fout.write(pkt)

        remaining = fin.read()
        if remaining:
            fout.write(remaining)

    return replaced_payloads

def read_wav_pcm(wav_path):
    """
    Returns the raw PCM bytes of a 16-bit / 48 kHz / stereo WAV file.
    Walks the RIFF chunks instead of assuming a 44-byte header: FFmpeg adds a
    LIST chunk by default (data starts at byte 78), and skipping a fixed 44
    bytes shifts the samples by half a frame and swaps the left/right channels.
    """
    with open(wav_path, 'rb') as f:
        riff = f.read(12)
        if len(riff) < 12 or riff[:4] != b'RIFF' or riff[8:12] != b'WAVE':
            raise ValueError(f"{wav_path} is not a RIFF/WAVE file")

        fmt = None
        while True:
            chunk_hdr = f.read(8)
            if len(chunk_hdr) < 8:
                raise ValueError(f"{wav_path} has no 'data' chunk")
            cid, csz = struct.unpack('<4sI', chunk_hdr)
            if cid == b'fmt ':
                fmt = struct.unpack('<HHIIHH', f.read(16))
                f.seek(csz - 16 + (csz & 1), os.SEEK_CUR)
            elif cid == b'data':
                if fmt is None:
                    raise ValueError(f"{wav_path}: 'data' chunk found before 'fmt ' chunk")
                tag, ch, rate, _, _, bits = fmt
                if tag != 1 or ch != 2 or rate != 48000 or bits != 16:
                    raise ValueError(
                        f"{wav_path}: expected 16-bit PCM, 48000 Hz, stereo "
                        f"(got tag={tag}, channels={ch}, rate={rate}, bits={bits})")
                pcm = f.read(csz)
                return pcm[:len(pcm) - (len(pcm) % 4)]
            else:
                f.seek(csz + (csz & 1), os.SEEK_CUR)

def patch_wmv_with_audio(orig_wmv_path, wav_path, out_wmv_path):
    """
    Main entry point: replaces the audio stream of orig_wmv_path with the audio from wav_path
    and saves to out_wmv_path.
    """
    hs, psz, block_align, tot_pkts, audio_payload_count = get_wmv_audio_info(orig_wmv_path)
    pcm_data = read_wav_pcm(wav_path)

    wma_blocks, block_timestamps = encode_pcm_to_wmapro(pcm_data, block_align, audio_payload_count)
    replaced = inject_audio_into_wmv(orig_wmv_path, wma_blocks, out_wmv_path, psz, block_align, tot_pkts, block_timestamps)
    return replaced == audio_payload_count
