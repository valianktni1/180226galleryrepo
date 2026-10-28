import { useEffect, useState } from 'react';
import { getBookingConnection, createBookingConnectionKey, saveBookingConnection, getErrorMessage } from '@/lib/api';
import { toast } from 'sonner';

export default function BookingConnection() {
  const [settings,setSettings]=useState(null),[key,setKey]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState('');
  useEffect(()=>{let current=true;getBookingConnection().then(r=>{if(current)setSettings(r.data)}).catch(()=>{if(current)setError('Could not load the connection. Reload Settings to retry.')});return()=>{current=false}},[]);
  async function run(action){setBusy(true);setError('');try{await action()}catch(e){setError(getErrorMessage(e,'Connection could not be saved.'))}finally{setBusy(false)}}
  if(!settings)return <p role="status">{error||'Loading booking connection…'}</p>;
  return <section className="max-w-xl space-y-5" style={{color:'var(--admin-text)'}}>
    <h2 className="text-xl font-semibold">Wedding booking connection</h2>
    <p>Creates private galleries and guest-upload QR links for new eligible Weddings By Mark bookings. It never emails couples or changes an existing gallery.</p>
    <p>Configure package folders in the booking app. Guest-upload links expire three days after the wedding, using the existing gallery expiry rule.</p>
    {error&&<p role="alert">{error}</p>}
    <p>Status: <strong>{settings.enabled?'Enabled':'Off'}</strong></p>
    <button type="button" disabled={busy} className="border rounded px-4 py-3" onClick={()=>{
      if(settings.key_saved&&!window.confirm('Replace the connection key? The booking connection will pause until you paste the new key into the booking app.'))return;
      run(async()=>{const r=await createBookingConnectionKey();setKey(r.data.key);setSettings({enabled:false,key_saved:true});toast.success('New key created. Enable the connection after copying it.');});
    }}>{settings.key_saved?'Replace connection key':'Create connection key'}</button>
    {key&&<div className="space-y-3"><label className="block" htmlFor="booking-connection-key">Copy this key into booking Settings → Wedding galleries. It is shown only now.</label><input id="booking-connection-key" type="password" readOnly autoComplete="off" value={key} className="border rounded p-3 w-full" style={{color:'var(--admin-text)',background:'var(--admin-bg)'}} onFocus={e=>e.target.select()}/><button type="button" className="border rounded px-4 py-3" onClick={()=>navigator.clipboard.writeText(key).then(()=>toast.success('Key copied')).catch(()=>setError('Select and copy the key manually.'))}>Copy key</button></div>}
    <div><button type="button" disabled={busy||!settings.key_saved} className="border rounded px-4 py-3" onClick={()=>run(async()=>{const enabled=!settings.enabled;await saveBookingConnection({enabled});setSettings({...settings,enabled});toast.success(enabled?'Booking connection enabled':'Booking connection paused');})}>{settings.enabled?'Pause connection':'Enable connection'}</button></div>
    <p className="text-sm">Keep your normal manual gallery controls. You still choose when to send the QR-design email.</p>
  </section>;
}
