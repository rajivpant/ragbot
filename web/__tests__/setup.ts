import '@testing-library/jest-dom/vitest';
import { afterEach } from 'vitest';
import { cleanup } from '@testing-library/react';

// jsdom does not implement scrollIntoView. Chat.tsx calls it inside its
// auto-scroll useEffect; tests would crash on every render without this stub.
if (typeof Element !== 'undefined' && !Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = function () {
    /* test stub */
  };
}

// Auto-cleanup the DOM between tests so component state doesn't leak.
afterEach(() => {
  cleanup();
});
