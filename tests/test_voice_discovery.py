import asyncio
import struct
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
import db
from voice_idle import discover_voice_ip, VoiceConnectionTimeout


class VoiceDiscoveryTests(unittest.IsolatedAsyncioTestCase):
    async def run_discovery(self, reply_on):
        callbacks = []
        loop = asyncio.get_running_loop()
        packet = bytearray(74)
        packet[:8] = struct.pack('>HHI', 2, 70, 123)
        packet[8:17] = b'127.0.0.1'
        struct.pack_into('>H', packet, 72, 5555)
        sent = 0

        async def send(sock, payload):
            nonlocal sent
            sent += 1
            self.assertTrue(callbacks, 'listener must be registered before sending')
            self.assertEqual(len(payload), 74)
            if sent == reply_on:
                callbacks[0](bytes(packet))
                callbacks[0](bytes(packet))  # Duplicate replies are safe.

        state = SimpleNamespace(ssrc=123, socket=object(), endpoint_ip='127.0.0.1', voice_port=5000,
                                add_socket_listener=callbacks.append, remove_socket_listener=callbacks.remove,
                                _socket_reader=SimpleNamespace(resume=Mock()))
        ws = SimpleNamespace(_connection=state, loop=loop)
        with patch.object(loop, 'sock_sendall', AsyncMock(side_effect=send)), \
             patch('voice_idle.DISCOVERY_TIMEOUT_SECONDS', .01):
            try:
                return await discover_voice_ip(ws), sent
            finally:
                self.assertEqual(callbacks, [])

    async def test_reply_on_first_packet(self):
        self.assertEqual(await self.run_discovery(1), (('127.0.0.1', 5555), 1))

    async def test_lost_packet_retries_without_leaving_channel(self):
        self.assertEqual(await self.run_discovery(2), (('127.0.0.1', 5555), 2))

    async def test_no_reply_gets_voice_specific_error(self):
        with self.assertRaises(VoiceConnectionTimeout):
            await self.run_discovery(99)
        self.assertEqual(db.error_code(VoiceConnectionTimeout(), 'music.search'), 'HB-M105')
