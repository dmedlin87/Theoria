# Theoria UI Guidelines

## Motion and Accessibility
- Respect the user's reduced motion preference. Interactive components rely on CSS custom properties (e.g., `--motion-hover-translate-y-sm`) so they animate when motion is enabled but stay still when `prefers-reduced-motion: reduce` is set.
- Within the reduced-motion media query we zero out the transition tokens (`--transition-*`) and motion transforms. This keeps hover and focus feedback available through color, border, and shadow changes without the movement side effects.
- When building new interactive elements, source transforms and transition timing from the shared tokens so they automatically inherit the reduced-motion behavior.
