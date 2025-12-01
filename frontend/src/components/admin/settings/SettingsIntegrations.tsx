import { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { useAppStore } from '../../../store/useAppStore';
import { FormInput } from '../../forms/FormInput';
import { FormTextarea } from '../../forms/FormTextarea'; 
import { Save, RefreshCw, CreditCard, Activity, Calendar, Image, CloudSun, Mail } from 'lucide-react';
import { toast } from 'react-toastify';

export function SettingsIntegrations() {
  const { settings, updateSettings, runFinanceSync, runMedNewsSync } = useAppStore();
  const { register, handleSubmit, reset } = useForm({
    defaultValues: settings,
  });
  
  useEffect(() => {
    reset(settings);
  }, [settings, reset]);

  const onSubmit = async (data: Record<string, any>) => {
    await updateSettings(data);
    toast.success("Integration settings saved.");
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-8 max-w-4xl animate-slide-up pb-20">
      
      {/* --- Header --- */}
      <div className="flex justify-between items-end border-b border-border-invisible pb-8">
        <div>
          <h2 className="text-3xl font-light text-txt-primary tracking-tight">Integrations</h2>
          <p className="text-txt-secondary mt-2 text-sm">Connect external services and data sources.</p>
        </div>
        <button 
          type="submit"
          className="flex items-center gap-2 px-6 py-3 bg-accent hover:bg-white text-void rounded-xl font-bold transition-all active:scale-95 shadow-glow uppercase tracking-widest text-xs"
        >
          <Save size={18} /> Save Changes
        </button>
      </div>

      {/* --- Immich (Photos) --- */}
      <section className="bg-surface p-8 rounded-[24px] border border-border-invisible shadow-float">
        <h3 className="text-xl font-light text-txt-primary mb-6 flex items-center gap-3 border-b border-border-invisible pb-6">
            <div className="p-2.5 bg-elevated rounded-xl text-accent"><Image size={20}/></div>
            Immich Photos
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          <FormInput 
            label="Server URL" 
            registration={register('immich_url')} 
            description="e.g. http://192.168.1.50:2283"
          />
          <FormInput 
            label="API Key" 
            type="password" 
            registration={register('immich_api_key')} 
          />
        </div>
      </section>

      {/* --- Weather --- */}
      <section className="bg-surface p-8 rounded-[24px] border border-border-invisible shadow-float">
        <h3 className="text-xl font-light text-txt-primary mb-6 flex items-center gap-3 border-b border-border-invisible pb-6">
            <div className="p-2.5 bg-elevated rounded-xl text-accent"><CloudSun size={20}/></div>
            Local Weather
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          <FormInput 
            label="Latitude" 
            registration={register('weather_location_lat')}
            description="e.g. 40.7128"
          />
          <FormInput 
            label="Longitude" 
            registration={register('weather_location_lon')} 
            description="e.g. -74.0060"
          />
        </div>
      </section>

      {/* --- Apple Calendar --- */}
      <section className="bg-surface p-8 rounded-[24px] border border-border-invisible shadow-float">
        <h3 className="text-xl font-light text-txt-primary mb-6 flex items-center gap-3 border-b border-border-invisible pb-6">
            <div className="p-2.5 bg-elevated rounded-xl text-accent"><Calendar size={20}/></div>
            Apple Calendar
        </h3>
        <p className="text-xs text-txt-tertiary mb-6">
            Requires App-Specific Password from <a href="https://appleid.apple.com" target="_blank" className="text-accent underline hover:text-white">appleid.apple.com</a>.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          <FormInput 
            label="CalDAV URL" 
            registration={register('caldav_url')} 
            description="Usually: https://caldav.icloud.com" 
          />
          <FormInput 
            label="iCloud Email" 
            type="email" 
            registration={register('caldav_username')} 
          />
          <FormInput 
            label="App-Specific Password" 
            type="password" 
            registration={register('caldav_password')} 
          />
          <FormInput 
            label="Calendar Name" 
            registration={register('caldav_calendar_name')} 
            description="Optional (Syncs all if empty)"
          />
        </div>
      </section>

      {/* --- Email --- */}
      <section className="bg-surface p-8 rounded-[24px] border border-border-invisible shadow-float">
        <h3 className="text-xl font-light text-txt-primary mb-6 flex items-center gap-3 border-b border-border-invisible pb-6">
             <div className="p-2.5 bg-elevated rounded-xl text-accent"><Mail size={20}/></div>
             Email Services
        </h3>
        
        <div className="mb-10">
            <h4 className="text-xs font-bold text-accent uppercase tracking-widest mb-6">Outbound (SMTP)</h4>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                <FormInput label="SMTP Server" registration={register('smtp_server')} />
                <FormInput label="SMTP Port" type="number" registration={register('smtp_port')} />
                <FormInput label="SMTP Email" type="email" registration={register('smtp_email')} />
                <FormInput label="SMTP Password" type="password" registration={register('smtp_password')} />
                <FormInput label="My Email" type="email" registration={register('recipient_email_chris')} />
                <FormInput label="Family Email" type="email" registration={register('recipient_email_family')} />
            </div>
        </div>

        <div className="pt-8 border-t border-border-invisible">
          <h4 className="text-xs font-bold text-accent uppercase tracking-widest mb-6">Inbound (IMAP)</h4>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            <FormInput label="IMAP Server" registration={register('imap_server')} />
            <FormInput label="IMAP Email" type="email" registration={register('imap_email')} />
            <FormInput label="IMAP Password" type="password" registration={register('imap_password')} />
            <div className="space-y-6">
               <FormInput label="Health Filter" registration={register('imap_subject_filter')} />
               <FormInput label="Sleep Filter" registration={register('imap_subject_filter_sleep')} />
            </div>
          </div>
        </div>
      </section>

      {/* --- YNAB --- */}
      <section className="bg-surface p-8 rounded-[24px] border border-border-invisible shadow-float">
        <h3 className="text-xl font-light text-txt-primary mb-6 flex items-center gap-3 border-b border-border-invisible pb-6">
             <div className="p-2.5 bg-elevated rounded-xl text-accent"><CreditCard size={20}/></div>
             YNAB Finance
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 items-end">
          <FormInput 
            label="Personal Access Token" 
            type="password" 
            registration={register('ynab_personal_token')} 
          />
          <FormTextarea 
            label="Track Categories (JSON)" 
            registration={register('ynab_categories_to_track')} 
            rows={1} 
            placeholder='["Groceries", "Gas"]'
          />
          <div className="pb-1">
             <button
              type="button"
              onClick={runFinanceSync}
              className="flex items-center gap-2 px-6 py-3 bg-elevated hover:bg-border-active text-txt-primary rounded-xl border border-border-subtle transition-colors text-xs font-bold uppercase tracking-wider shadow-sm active:scale-95"
            >
              <RefreshCw size={14} /> Sync Now
            </button>
          </div>
        </div>
      </section>
      
      {/* --- RSS Feeds --- */}
      <section className="bg-surface p-8 rounded-[24px] border border-border-invisible shadow-float">
        <h3 className="text-xl font-light text-txt-primary mb-6 flex items-center gap-3 border-b border-border-invisible pb-6">
             <div className="p-2.5 bg-elevated rounded-xl text-accent"><Activity size={20}/></div>
             Clinical Pearls & News
        </h3>
        <div className="space-y-8">
          <FormTextarea label="EM RSS Feeds (JSON)" registration={register('em_rss_feeds')} rows={2} />
          <FormTextarea label="General RSS Feeds (JSON)" registration={register('general_rss_feeds')} rows={2} />
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
             <FormTextarea label="Summary Prompt" registration={register('med_news_summary_prompt')} rows={3} />
             <FormTextarea label="Refresher Prompt" registration={register('med_news_refresher_prompt')} rows={3} />
          </div>
          <div>
             <button
              type="button"
              onClick={runMedNewsSync}
              className="flex items-center gap-2 px-6 py-3 bg-elevated hover:bg-border-active text-txt-primary rounded-xl border border-border-subtle transition-colors text-xs font-bold uppercase tracking-wider shadow-sm active:scale-95"
            >
              <RefreshCw size={14} /> Sync News
            </button>
          </div>
        </div>
      </section>
    </form>
  );
}