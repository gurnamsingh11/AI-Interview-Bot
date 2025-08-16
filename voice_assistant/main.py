import asyncio
import traceback
import pyaudio
from collections import deque
import random

from google.genai import types
from voice_assistant.config import JD, CR, prompt, MODEL, client

FORMAT = pyaudio.paInt16
RECEIVE_SAMPLE_RATE = 24000
SEND_SAMPLE_RATE = 16000
CHUNK_SIZE = 512
CHANNELS = 1

from google.genai.types import (
    LiveConnectConfig,
    SpeechConfig,
    VoiceConfig,
    PrebuiltVoiceConfig,
    FunctionDeclaration,
    Tool,
)

# Global stop event for controlling the audio loop
_stop_event = None


def set_stop_event(stop_event):
    """Set the global stop event for controlling audio loop"""
    global _stop_event
    _stop_event = stop_event


def _should_stop():
    """Check if we should stop the audio processing"""
    global _stop_event
    return _stop_event and _stop_event.is_set()


# Mock function for get_order_status (exactly as your original)
def get_order_status(order_id):
    """Mock order status API that returns randomized status for an order ID."""
    statuses = ["processing", "shipped", "delivered"]
    shipment_methods = ["standard", "express", "next day", "international"]

    seed = sum(ord(c) for c in str(order_id))
    random.seed(seed)

    status = random.choice(statuses)
    shipment = random.choice(shipment_methods)
    order_date = "2024-05-" + str(random.randint(12, 28)).zfill(2)

    estimated_delivery = None
    shipped_date = None
    delivered_date = None

    if status == "processing":
        estimated_delivery = "2024-06-" + str(random.randint(1, 15)).zfill(2)
    elif status == "shipped":
        shipped_date = "2024-05-" + str(random.randint(1, 28)).zfill(2)
        estimated_delivery = "2024-06-" + str(random.randint(1, 15)).zfill(2)
    elif status == "delivered":
        shipped_date = "2024-05-" + str(random.randint(1, 20)).zfill(2)
        delivered_date = "2024-05-" + str(random.randint(21, 28)).zfill(2)

    random.seed()

    result = {
        "order_id": order_id,
        "status": status,
        "order_date": order_date,
        "shipment_method": shipment,
        "estimated_delivery": estimated_delivery,
    }

    if shipped_date:
        result["shipped_date"] = shipped_date
    if delivered_date:
        result["delivered_date"] = delivered_date

    print(f"Order status for {order_id}: {status}")
    return result


# Define the order status tool (exactly as your original)
order_status_tool = Tool(
    function_declarations=[
        FunctionDeclaration(
            name="get_order_status",
            description="Get the current status and details of an order.",
            parameters={
                "type": "OBJECT",
                "properties": {
                    "order_id": {
                        "type": "STRING",
                        "description": "The order ID to look up.",
                    }
                },
                "required": ["order_id"],
            },
        )
    ]
)

CONFIG = LiveConnectConfig(
    response_modalities=["AUDIO"],
    output_audio_transcription={},
    input_audio_transcription={},
    speech_config=SpeechConfig(
        voice_config=VoiceConfig(
            prebuilt_voice_config=PrebuiltVoiceConfig(voice_name="Puck")
        )
    ),
    system_instruction=prompt(JD, CR),
    tools=[order_status_tool],
)


class AudioManager:
    def __init__(self, input_sample_rate=16000, output_sample_rate=24000):
        self.pya = pyaudio.PyAudio()
        self.input_stream = None
        self.output_stream = None
        self.input_sample_rate = input_sample_rate
        self.output_sample_rate = output_sample_rate
        self.audio_queue = deque()
        self.is_playing = False
        self.playback_task = None

    async def initialize(self):
        mic_info = self.pya.get_default_input_device_info()
        print(f"microphone used: {mic_info}")

        self.input_stream = await asyncio.to_thread(
            self.pya.open,
            format=FORMAT,
            channels=CHANNELS,
            rate=self.input_sample_rate,
            input=True,
            input_device_index=mic_info["index"],
            frames_per_buffer=CHUNK_SIZE,
        )

        self.output_stream = await asyncio.to_thread(
            self.pya.open,
            format=FORMAT,
            channels=CHANNELS,
            rate=self.output_sample_rate,
            output=True,
        )

    def add_audio(self, audio_data):
        """Add audio data to the playback queue"""
        self.audio_queue.append(audio_data)

        if self.playback_task is None or self.playback_task.done():
            self.playback_task = asyncio.create_task(self.play_audio())

    async def play_audio(self):
        """Play all queued audio data"""
        print("🗣️ Gemini talking")
        while self.audio_queue and not _should_stop():
            try:
                audio_data = self.audio_queue.popleft()
                await asyncio.to_thread(self.output_stream.write, audio_data)
            except Exception as e:
                print(f"Error playing audio: {e}")
                break

        self.is_playing = False

    def interrupt(self):
        """Handle interruption by stopping playback and clearing queue"""
        self.audio_queue.clear()
        self.is_playing = False

        if self.playback_task and not self.playback_task.done():
            self.playback_task.cancel()

    async def cleanup(self):
        """Cleanup audio resources"""
        print("🔧 Cleaning up audio resources...")

        self.interrupt()

        if self.input_stream:
            await asyncio.to_thread(self.input_stream.stop_stream)
            await asyncio.to_thread(self.input_stream.close)

        if self.output_stream:
            await asyncio.to_thread(self.output_stream.stop_stream)
            await asyncio.to_thread(self.output_stream.close)

        await asyncio.to_thread(self.pya.terminate)
        print("✅ Audio cleanup complete")


async def audio_loop():
    """Main audio loop - based on your original with stop control added"""
    audio_manager = AudioManager(
        input_sample_rate=SEND_SAMPLE_RATE, output_sample_rate=RECEIVE_SAMPLE_RATE
    )

    try:
        await audio_manager.initialize()

        async with (
            client.aio.live.connect(model=MODEL, config=CONFIG) as session,
            asyncio.TaskGroup() as tg,
        ):
            # Queue for user audio chunks to control flow
            audio_queue = asyncio.Queue()

            async def listen_for_audio():
                """Just captures audio and puts it in the queue"""
                while not _should_stop():
                    try:
                        data = await asyncio.to_thread(
                            audio_manager.input_stream.read,
                            CHUNK_SIZE,
                            exception_on_overflow=False,
                        )
                        await audio_queue.put(data)
                    except Exception as e:
                        if not _should_stop():
                            print(f"Error in audio capture: {e}")
                        break

            async def process_and_send_audio():
                """Processes audio from queue and sends to Gemini"""
                while not _should_stop():
                    try:
                        data = await audio_queue.get()

                        # Always send the audio data to Gemini
                        await session.send_realtime_input(
                            media={
                                "data": data,
                                "mime_type": f"audio/pcm;rate={SEND_SAMPLE_RATE}",
                            }
                        )
                        audio_queue.task_done()

                    except Exception as e:
                        if not _should_stop():
                            print(f"Error in audio processing: {e}")
                        break

            async def receive_and_play():
                """Receive responses and play audio - your original logic"""
                while not _should_stop():
                    try:
                        input_transcriptions = []
                        output_transcriptions = []

                        async for response in session.receive():
                            if _should_stop():
                                break

                            # retrieve continously resumable session ID
                            if response.session_resumption_update:
                                update = response.session_resumption_update
                                if update.resumable and update.new_handle:
                                    print(f"new SESSION: {update.new_handle}")

                            # Check if the connection will be soon terminated
                            if response.go_away is not None:
                                print(response.go_away.time_left)

                            # Handle tool calls
                            if response.tool_call:
                                print(f"🔧 Tool call received: {response.tool_call}")

                                function_responses = []

                                for function_call in response.tool_call.function_calls:
                                    name = function_call.name
                                    args = function_call.args
                                    call_id = function_call.id

                                    # Handle get_order_status function
                                    if name == "get_order_status":
                                        try:
                                            order_id = args["order_id"]
                                            result = get_order_status(order_id)

                                            function_responses.append(
                                                {
                                                    "name": name,
                                                    "response": {"result": result},
                                                    "id": call_id,
                                                }
                                            )

                                            print(
                                                f"📦 Order status function executed for order {order_id}"
                                            )

                                        except Exception as e:
                                            print(
                                                f"Error executing order status function: {e}"
                                            )
                                            traceback.print_exc()

                                # Send function responses back to Gemini
                                if function_responses:
                                    print(
                                        f"Sending function responses: {function_responses}"
                                    )
                                    for response in function_responses:
                                        await session.send_tool_response(
                                            function_responses={
                                                "name": response["name"],
                                                "response": response["response"][
                                                    "result"
                                                ],
                                                "id": response["id"],
                                            }
                                        )
                                    continue

                            server_content = response.server_content

                            if (
                                hasattr(server_content, "interrupted")
                                and server_content.interrupted
                            ):
                                print(f"🤐 INTERRUPTION DETECTED")
                                audio_manager.interrupt()

                            if server_content and server_content.model_turn:
                                for part in server_content.model_turn.parts:
                                    if part.inline_data:
                                        audio_manager.add_audio(part.inline_data.data)

                            if server_content and server_content.turn_complete:
                                print("✅ Gemini done talking")

                            output_transcription = getattr(
                                response.server_content, "output_transcription", None
                            )
                            if output_transcription and output_transcription.text:
                                output_transcriptions.append(output_transcription.text)

                            input_transcription = getattr(
                                response.server_content, "input_transcription", None
                            )
                            if input_transcription and input_transcription.text:
                                input_transcriptions.append(input_transcription.text)

                        # Print transcriptions (your original logic)
                        if output_transcriptions:
                            print(
                                f"Output transcription: {''.join(output_transcriptions)}"
                            )
                        if input_transcriptions:
                            print(
                                f"Input transcription: {''.join(input_transcriptions)}"
                            )

                    except Exception as e:
                        if not _should_stop():
                            print(f"Error in receive_and_play: {e}")
                            traceback.print_exc()
                        break

            # Start all tasks with proper task creation
            tg.create_task(listen_for_audio())
            tg.create_task(process_and_send_audio())
            tg.create_task(receive_and_play())

    except Exception as e:
        print(f"Error in audio loop: {e}")
        traceback.print_exc()
    finally:
        # Always cleanup
        await audio_manager.cleanup()
        print("🛑 Audio loop stopped")


def run_audio_loop():
    """Run the audio loop with error handling."""
    try:
        asyncio.run(audio_loop(), debug=False)
    except KeyboardInterrupt:
        print("Exiting application via KeyboardInterrupt...")
    except Exception as e:
        print(f"Unhandled exception in audio loop: {e}")
        traceback.print_exc()
    finally:
        print("Audio loop thread exiting...")
