import { render } from '@testing-library/react';
import { expectNoA11yViolations } from '../../test/axe-helper';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '../ui/Dialog';
import { Button } from '../ui/Button';

describe('Dialog accessibility', () => {
  it('has no a11y violations when open', async () => {
    const { container } = render(
      <Dialog open onOpenChange={() => {}}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Test Dialog</DialogTitle>
          </DialogHeader>
          <p>Dialog body content</p>
          <DialogFooter>
            <Button>Confirm</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    );
    await expectNoA11yViolations(container);
  });
});
