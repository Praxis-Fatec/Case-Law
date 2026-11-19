import { useEffect, type RefObject } from 'react';

export function useDialog(dialog: RefObject<HTMLDialogElement>, returnFocusId: string) {
  useEffect(() => {
    const element = dialog.current!;
    element.showModal();
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      element.close();
      document.body.style.overflow = overflow;
      document.getElementById(returnFocusId)?.focus();
    };
  }, [dialog, returnFocusId]);
}
