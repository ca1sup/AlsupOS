import { Fragment } from 'react';
import { Dialog, Transition } from '@headlessui/react';
import { X, FileText } from 'lucide-react';
import { useAppStore } from '../store/useAppStore';

export function SourceModal() {
  const { isSourceModalOpen, sourceModalContent, closeSourceModal } = useAppStore();

  return (
    <Transition appear show={isSourceModalOpen} as={Fragment}>
      <Dialog as="div" className="relative z-50" onClose={closeSourceModal}>
        <Transition.Child
          as={Fragment}
          enter="ease-out duration-300"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in duration-200"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div className="fixed inset-0 bg-black/60 backdrop-blur-sm" />
        </Transition.Child>

        <div className="fixed inset-0 overflow-y-auto">
          <div className="flex min-h-full items-center justify-center p-4 text-center">
            <Transition.Child
              as={Fragment}
              enter="ease-out duration-300"
              enterFrom="opacity-0 scale-95"
              enterTo="opacity-100 scale-100"
              leave="ease-in duration-200"
              leaveFrom="opacity-100 scale-100"
              leaveTo="opacity-0 scale-95"
            >
              <Dialog.Panel className="w-full max-w-3xl transform overflow-hidden rounded-2xl bg-warm-surface p-6 text-left align-middle shadow-2xl border border-warm-border transition-all">
                <div className="flex items-center justify-between mb-4 border-b border-warm-border/50 pb-4">
                  <Dialog.Title as="h3" className="text-lg font-semibold text-warm-text-primary flex items-center gap-2">
                    <FileText size={20} className="text-pastel-slate" />
                    <span className="truncate">{sourceModalContent.title}</span>
                  </Dialog.Title>
                  <button
                    onClick={closeSourceModal}
                    className="rounded-full p-1 text-warm-text-secondary hover:bg-warm-hover transition-colors"
                  >
                    <X size={20} />
                  </button>
                </div>
                
                <div className="mt-2 max-h-[65vh] overflow-y-auto custom-scrollbar bg-warm-main rounded-lg border border-warm-border p-4">
                  <pre className="whitespace-pre-wrap font-sans text-sm text-warm-text-primary leading-relaxed">
                    {sourceModalContent.content}
                  </pre>
                </div>
              </Dialog.Panel>
            </Transition.Child>
          </div>
        </div>
      </Dialog>
    </Transition>
  );
}