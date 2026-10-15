import { useEffect, useRef, useState } from "react";
import { ArrowLeft, Check, Loader2, Mic2, RotateCcw, Send, Square } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { getErrorMessage, uploadVoiceMessage } from "@/lib/api";

const MAX_SECONDS = 240;
const WARNING_SECONDS = 210;

const formatTime = (seconds) => {
  const whole = Math.max(0, Math.floor(seconds || 0));
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, '0')}`;
};

const preferredMimeTypes = () => {
  const choices = [
    'audio/webm;codecs=opus',
    'audio/mp4;codecs=mp4a.40.2',
    'audio/mp4',
    'audio/webm',
    'audio/ogg;codecs=opus',
    'audio/ogg',
  ];
  if (!window.MediaRecorder?.isTypeSupported) return [];
  return choices.filter((type) => window.MediaRecorder.isTypeSupported(type));
};

const createAudioRecorder = (stream) => {
  const attempts = preferredMimeTypes().flatMap((mimeType) => [
    { mimeType, audioBitsPerSecond: 192000 },
    { mimeType },
  ]);
  attempts.push({ audioBitsPerSecond: 192000 }, {});

  for (const options of attempts) {
    try {
      return {
        recorder: new MediaRecorder(stream, options),
        requestedMimeType: options.mimeType || '',
      };
    } catch (error) {
      // Some mobile browsers report a MIME type as supported but reject it
      // when the recorder is created. Try the next safe option.
    }
  }
  throw new Error('No compatible audio recorder configuration is available');
};

const recordingName = (mimeType) => {
  if (mimeType.includes('mp4')) return 'personal-message.m4a';
  if (mimeType.includes('ogg')) return 'personal-message.ogg';
  return 'personal-message.webm';
};

export default function VoiceMessageRecorder({ token, coupleName, darkMode, onBack, onComplete }) {
  const recorderRef = useRef(null);
  const streamRef = useRef(null);
  const timerRef = useRef(null);
  const chunksRef = useRef([]);
  const startedAtRef = useRef(0);
  const objectUrlRef = useRef(null);

  const [stage, setStage] = useState('ready');
  const [guestName, setGuestName] = useState('');
  const [elapsed, setElapsed] = useState(0);
  const [recordedDuration, setRecordedDuration] = useState(0);
  const [recordingFile, setRecordingFile] = useState(null);
  const [audioUrl, setAudioUrl] = useState(null);
  const [uploadProgress, setUploadProgress] = useState(0);

  const colours = darkMode ? {
    bg: '#171717', card: '#242424', text: '#FAFAF9', muted: '#C4C0B8', border: '#3F3F46', accent: '#D4AF37', soft: 'rgba(212,175,55,0.12)'
  } : {
    bg: '#FDFCF8', card: '#FFFFFF', text: '#1C1917', muted: '#57534E', border: '#E7E5E4', accent: '#D4AF37', soft: 'rgba(212,175,55,0.09)'
  };

  const stopTracks = () => {
    streamRef.current?.getTracks?.().forEach((track) => track.stop());
    streamRef.current = null;
  };

  const clearTimer = () => {
    if (timerRef.current) window.clearInterval(timerRef.current);
    timerRef.current = null;
  };

  const clearPreview = () => {
    if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current);
    objectUrlRef.current = null;
    setAudioUrl(null);
    setRecordingFile(null);
  };

  useEffect(() => () => {
    clearTimer();
    if (recorderRef.current?.state === 'recording') recorderRef.current.stop();
    stopTracks();
    if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current);
  }, []);

  const finishRecording = () => {
    const recorder = recorderRef.current;
    if (recorder?.state === 'recording') recorder.stop();
  };

  const startRecording = async () => {
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      toast.error('Voice recording is not supported by this browser');
      return;
    }
    clearPreview();
    setElapsed(0);
    chunksRef.current = [];
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: { ideal: 2 },
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      if (!stream.getAudioTracks?.().length) {
        throw new Error('The browser did not provide an audio track');
      }
      streamRef.current = stream;
      const { recorder, requestedMimeType } = createAudioRecorder(stream);
      recorderRef.current = recorder;
      recorder.ondataavailable = (event) => {
        if (event.data?.size) chunksRef.current.push(event.data);
      };
      recorder.onerror = () => {
        clearTimer();
        stopTracks();
        setStage('ready');
        toast.error('The recording stopped unexpectedly. Please try again.');
      };
      recorder.onstop = () => {
        clearTimer();
        stopTracks();
        const duration = Math.min(MAX_SECONDS, Math.max(1, (Date.now() - startedAtRef.current) / 1000));
        const capturedType = chunksRef.current.find((chunk) => chunk.type)?.type || '';
        const finalType = recorder.mimeType || capturedType || requestedMimeType || 'audio/webm';
        const blob = new Blob(chunksRef.current, { type: finalType });
        if (!blob.size) {
          setStage('ready');
          toast.error('No audio was captured. Please try again.');
          return;
        }
        const file = new File([blob], recordingName(finalType), { type: finalType });
        const url = URL.createObjectURL(blob);
        objectUrlRef.current = url;
        setRecordingFile(file);
        setAudioUrl(url);
        setRecordedDuration(duration);
        setElapsed(duration);
        setStage('review');
      };
      startedAtRef.current = Date.now();
      // A single final Blob is more reliable than concatenated timed chunks on
      // iOS Safari, Samsung Internet and several Android Chromium variants.
      recorder.start();
      setStage('recording');
      timerRef.current = window.setInterval(() => {
        const next = Math.min(MAX_SECONDS, (Date.now() - startedAtRef.current) / 1000);
        setElapsed(next);
        if (next >= MAX_SECONDS && recorder.state === 'recording') recorder.stop();
      }, 250);
    } catch (error) {
      stopTracks();
      setStage('ready');
      if (error?.name === 'NotAllowedError') {
        toast.error('Microphone access was not allowed. Please enable it and try again.');
      } else {
        toast.error('We could not start your microphone. Please try again.');
      }
    }
  };

  const recordAgain = () => {
    clearPreview();
    setElapsed(0);
    setRecordedDuration(0);
    setStage('ready');
  };

  const sendMessage = async () => {
    if (!guestName.trim()) {
      toast.error('Please enter your name before sending your message');
      return;
    }
    if (!recordingFile) return;
    setStage('uploading');
    setUploadProgress(0);
    try {
      await uploadVoiceMessage(token, recordingFile, guestName.trim(), recordedDuration, (event) => {
        if (event.total) setUploadProgress(Math.round((event.loaded * 100) / event.total));
      });
      setUploadProgress(100);
      clearPreview();
      setStage('success');
    } catch (error) {
      setStage('review');
      toast.error(getErrorMessage(error, 'Your message could not be sent. Please try again.'));
    }
  };

  const remaining = Math.max(0, MAX_SECONDS - elapsed);
  const warning = stage === 'recording' && elapsed >= WARNING_SECONDS;

  return (
    <div className="w-full max-w-lg mx-auto text-center flex-1 px-5 py-10" style={{ color: colours.text }} data-testid="voice-message-recorder">
      <button
        type="button"
        onClick={onBack}
        disabled={stage === 'recording' || stage === 'uploading'}
        className="inline-flex items-center gap-2 text-sm mb-6 disabled:opacity-40"
        style={{ color: colours.muted }}
      >
        <ArrowLeft className="w-4 h-4" /> Back to choices
      </button>

      <div className="rounded-2xl border p-6 sm:p-8 shadow-sm" style={{ backgroundColor: colours.card, borderColor: colours.border }}>
        {stage === 'success' ? (
          <div className="py-5">
            <div className="w-20 h-20 rounded-full mx-auto mb-5 flex items-center justify-center" style={{ backgroundColor: colours.accent }}>
              <Check className="w-10 h-10 text-white" strokeWidth={3} />
            </div>
            <h2 className="text-3xl font-medium mb-3" style={{ fontFamily: 'Cormorant Garamond, serif' }}>Message Sent!</h2>
            <p className="text-sm leading-relaxed mb-6" style={{ color: colours.muted }}>
              Thank you — your personal message for {coupleName} has been saved safely.
            </p>
            <div className="flex flex-col sm:flex-row justify-center gap-3">
              <Button variant="outline" onClick={() => { setGuestName(''); setElapsed(0); setStage('ready'); }}>
                Record Another Message
              </Button>
              <Button onClick={() => onComplete?.()} style={{ backgroundColor: colours.accent, color: 'white' }}>
                Back to Sharing Choices
              </Button>
            </div>
          </div>
        ) : (
          <>
            <div className="w-16 h-16 rounded-full mx-auto mb-4 flex items-center justify-center" style={{ backgroundColor: colours.soft }}>
              <Mic2 className="w-8 h-8" style={{ color: colours.accent }} />
            </div>
            <h2 className="text-3xl font-medium mb-2" style={{ fontFamily: 'Cormorant Garamond, serif' }}>Record Your Personal Message</h2>
            <p className="text-sm leading-relaxed mb-6" style={{ color: colours.muted }}>
              Share a memory, some advice or a heartfelt message for {coupleName}. You have up to four minutes.
            </p>

            {stage === 'ready' && (
              <>
                <button
                  type="button"
                  onClick={startRecording}
                  className="w-28 h-28 rounded-full mx-auto flex flex-col items-center justify-center text-white shadow-lg active:scale-95 transition-transform"
                  style={{ backgroundColor: '#B91C1C' }}
                  data-testid="start-voice-recording"
                >
                  <Mic2 className="w-9 h-9 mb-1" />
                  <span className="text-xs font-bold uppercase tracking-wider">Record</span>
                </button>
                <p className="text-xs mt-5" style={{ color: colours.muted }}>Your browser will ask for microphone permission.</p>
              </>
            )}

            {stage === 'recording' && (
              <div>
                <div className="flex items-center justify-center gap-2 mb-3">
                  <span className="w-3 h-3 rounded-full bg-red-600 animate-pulse" />
                  <span className="text-sm font-bold uppercase tracking-widest text-red-600">Recording</span>
                </div>
                <p className="text-5xl font-light tabular-nums mb-2">{formatTime(elapsed)}</p>
                <p className="text-xs mb-5" style={{ color: warning ? '#DC2626' : colours.muted }}>
                  {warning ? `${formatTime(remaining)} remaining — recording stops automatically at 4:00` : `${formatTime(remaining)} remaining`}
                </p>
                <Progress value={(elapsed / MAX_SECONDS) * 100} className="h-2 mb-6" />
                <button
                  type="button"
                  onClick={finishRecording}
                  className="w-20 h-20 rounded-full mx-auto flex flex-col items-center justify-center text-white bg-red-700"
                  data-testid="stop-voice-recording"
                >
                  <Square className="w-7 h-7 mb-1" fill="white" />
                  <span className="text-[10px] font-bold uppercase">Stop</span>
                </button>
              </div>
            )}

            {(stage === 'review' || stage === 'uploading') && (
              <div>
                <p className="text-sm font-semibold mb-2">Listen before you send</p>
                <audio controls preload="metadata" src={audioUrl || undefined} className="w-full mb-5" data-testid="voice-message-preview" />
                <Input
                  value={guestName}
                  onChange={(event) => setGuestName(event.target.value)}
                  placeholder="Your name"
                  maxLength={80}
                  disabled={stage === 'uploading'}
                  className="text-center mb-4"
                  style={{ backgroundColor: colours.bg, color: colours.text, borderColor: colours.border }}
                  data-testid="voice-guest-name"
                />
                {stage === 'uploading' ? (
                  <div className="py-4">
                    <Loader2 className="w-7 h-7 animate-spin mx-auto mb-3" style={{ color: colours.accent }} />
                    <p className="text-sm mb-3">Preparing your MP3… {uploadProgress}%</p>
                    <Progress value={uploadProgress} className="h-2" />
                  </div>
                ) : (
                  <div className="grid grid-cols-2 gap-3">
                    <Button variant="outline" onClick={recordAgain} className="gap-2" data-testid="rerecord-voice-message">
                      <RotateCcw className="w-4 h-4" /> Re-record
                    </Button>
                    <Button onClick={sendMessage} className="gap-2 text-white" style={{ backgroundColor: colours.accent }} data-testid="send-voice-message">
                      <Send className="w-4 h-4" /> Send Message
                    </Button>
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>
      <p className="text-[11px] mt-4 leading-relaxed" style={{ color: colours.muted }}>
        Your final message is saved as a normalised stereo MP3. The temporary browser recording is removed after conversion.
      </p>
    </div>
  );
}

