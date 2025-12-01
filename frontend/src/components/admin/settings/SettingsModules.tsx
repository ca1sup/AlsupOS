import { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { useAppStore } from '../../../store/useAppStore';
import { FormToggle } from '../../forms/FormToggle';
import { LayoutGrid, Save } from 'lucide-react';
import { toast } from 'react-toastify';

export function SettingsModules() {
  const { settings, updateSettings } = useAppStore();
  const { control, handleSubmit, reset } = useForm({
    defaultValues: settings,
  });

  useEffect(() => {
    reset(settings);
  }, [settings, reset]);

  const onSubmit = async (data: Record<string, any>) => {
    await updateSettings(data);
    toast.success("Modules updated successfully.");
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-8 max-w-4xl animate-slide-up">
      <section className="bg-surface p-8 rounded-[24px] border border-border-invisible shadow-float">
        <h3 className="text-xl font-light text-txt-primary mb-6 flex items-center gap-3 border-b border-border-invisible pb-6">
          <div className="p-2.5 bg-elevated rounded-xl text-accent"><LayoutGrid size={20} /></div>
          Active Modules
        </h3>
        <p className="text-sm text-txt-secondary mb-10">
          Enable or disable core features to customize the system's capabilities.
        </p>
        
        <div className="space-y-8 divide-y divide-border-invisible">
          <div className="pt-6 first:pt-0">
            <FormToggle 
              control={control} 
              name="module_finance_enabled" 
              label="Finance Tracking" 
              tooltip="Enables YNAB integration and budget queries."
            />
          </div>
          <div className="pt-6">
            <FormToggle 
              control={control} 
              name="module_workout_enabled" 
              label="Workout Logger" 
              tooltip="Tracks fitness stats and workout history."
            />
          </div>
          <div className="pt-6">
            <FormToggle 
              control={control} 
              name="module_worship_enabled" 
              label="Family Worship" 
              tooltip="Provides Bible reading plans and worship suggestions."
            />
          </div>
          <div className="pt-6">
            <FormToggle 
              control={control} 
              name="module_homeschool_enabled" 
              label="Homeschooling" 
              tooltip="Helps manage lesson plans and student progress."
            />
          </div>
          <div className="pt-6">
            <FormToggle 
              control={control} 
              name="module_clinical_pearl_enabled" 
              label="Clinical Pearls" 
              tooltip="Medical education module for daily clinical tips."
            />
          </div>
          
          {/* New Modules Section */}
          <div className="pt-10">
             <h4 className="text-[10px] font-bold text-txt-tertiary uppercase tracking-widest mb-6">Advanced Integrations</h4>
             <div className="space-y-8">
                 <FormToggle 
                    control={control} 
                    name="module_email_enabled" 
                    label="Email Sending (SMTP)" 
                    tooltip="Required for Daily Briefings and Alerts."
                 />
                 <FormToggle 
                    control={control} 
                    name="module_python_agent_enabled" 
                    label="Agent Python Playground" 
                    tooltip="Allows the AI to write and execute Python code for complex tasks."
                 />
                 <FormToggle 
                    control={control} 
                    name="module_apple_health_enabled" 
                    label="Apple Health Integration" 
                    tooltip="Processes health data exported via email."
                 />
                 <FormToggle 
                    control={control} 
                    name="module_immich_enabled" 
                    label="Immich Photo Integration" 
                    tooltip="Enables searching your personal photo library."
                 />
             </div>
          </div>
        </div>
      </section>

      <div className="pt-6 flex justify-end">
        <button
          type="submit"
          className="flex items-center gap-2 px-8 py-4 bg-accent text-void font-bold rounded-xl hover:bg-white transition-all shadow-glow uppercase tracking-widest text-xs active:scale-95"
        >
          <Save size={18} /> Save Modules
        </button>
      </div>
    </form>
  );
}