> **Archived on October 26, 2025** - UI enhancements manual testing checklist. This was used during development and is preserved for reference.

# UI Enhancements - Manual Test Checklist

Run through this checklist after starting the dev server to verify all enhancements work correctly.

## Prerequisites
```powershell
cd theo\services\web
npm run dev
```

Then visit http://localhost:3000

---

## ✅ Test 1: Theme Toggle

### Steps:
1. Scroll to the bottom of any page
2. Look for the theme toggle in the footer (next to copyright text)
3. Click **☀** (Light theme)
   - Page should be in light mode
4. Click **☾** (Dark theme)
   - Page should transition to dark mode
5. Click **◐** (Auto theme)
   - Should match your system theme
6. **Reload the page** (F5)
   - Theme selection should persist

### Expected Results:
- [ ] Theme toggle is visible in footer
- [ ] Clicking each button changes the theme
- [ ] Smooth transition animation (300ms)
- [ ] Theme persists after page reload
- [ ] Active button is highlighted in accent color

### Troubleshooting:
- If toggle not visible: Check AppShell.tsx footer has footerMeta wrapper
- If not persisting: Check browser console for localStorage errors

---

## ✅ Test 2: Command Palette

### Steps:
1. Press **⌘K** (Mac) or **Ctrl+K** (Windows/Linux)
   - Command palette should open
2. Type "chat"
   - Should filter to "Open chat"
3. Press **Enter** or click the item
   - Should navigate to /chat
4. Open palette again (⌘K)
5. Press **Escape**
   - Should close palette

### Expected Results:
- [ ] Keyboard shortcut opens palette
- [ ] Search filters commands correctly
- [ ] Can navigate with keyboard (↑↓ arrows)
- [ ] Pressing Enter navigates
- [ ] Escape closes palette
- [ ] Backdrop blur effect visible
- [ ] Focus returns to page after closing

### Troubleshooting:
- If not opening: Check CommandPalette is rendered in AppShell
- If search broken: Check cmdk package is installed (`npm list cmdk`)

---

## ✅ Test 3: Command Bar Trigger Button

### Steps:
1. Look at the top command bar (below navigation)
2. Find the "Quick actions..." button with ⌘K badge
3. Click the button
   - Command palette should open

### Expected Results:
- [ ] Trigger button is visible in command bar
- [ ] Shows keyboard shortcut badge (⌘K)
- [ ] Hover shows accent color
- [ ] Click opens command palette

---

## ✅ Test 4: PWA Manifest

### Steps:
1. Open **DevTools** (F12)
2. Go to **Application** tab (Chrome) or **Storage** tab (Firefox)
3. Click **Manifest** in the sidebar
4. Verify manifest loads

### Expected Results:
- [ ] Manifest loads without errors
- [ ] Name: "Theoria Research Engine"
- [ ] Short name: "Theoria"
- [ ] Theme color: #6366f1
- [ ] Start URL: /

### Icon Warnings (Expected):
- ⚠️ You'll see warnings about missing icons (icon-192.png, etc.)
- This is normal - icons need to be created separately
- Manifest will still work for other features

---

## ✅ Test 5: Animation Utilities

### Steps:
1. Open DevTools → Elements/Inspector
2. Add test classes to any element using DevTools:
   - Add class `fade-in` → Should fade in
   - Add class `slide-up` → Should slide up
   - Add class `pulse` → Should pulse continuously

### Expected Results:
- [ ] Animation classes apply correctly
- [ ] Animations are smooth (60fps)
- [ ] Multiple animations can be combined

### Quick Test Element:
Open console and run:
```javascript
// Create test element
const test = document.createElement('div');
test.className = 'fade-in slide-up';
test.style.cssText = 'position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);padding:2rem;background:#6366f1;color:white;border-radius:0.5rem;z-index:9999;';
test.textContent = 'Animation Test! (Will auto-remove)';
document.body.appendChild(test);
setTimeout(() => test.remove(), 3000);
```

---

## ✅ Test 6: Reduced Motion

### Steps:
1. Enable reduced motion:
   - **Windows**: Settings → Accessibility → Visual effects → Animation effects OFF
   - **Mac**: System Preferences → Accessibility → Display → Reduce motion
   - **Linux**: System Settings → Accessibility → Animations
2. Reload the page
3. Test theme toggle and command palette

### Expected Results:
- [ ] Animations are instant (no delays)
- [ ] Functionality still works
- [ ] No jarring motion

---

## ✅ Test 7: Mobile Responsiveness

### Steps:
1. Open DevTools (F12)
2. Toggle device toolbar (Ctrl+Shift+M or ⌘+Shift+M)
3. Select "iPhone 12 Pro" or similar
4. Test all features on mobile viewport

### Expected Results:
- [ ] Theme toggle is visible on mobile
- [ ] Command palette works with mobile viewport
- [ ] Trigger button is accessible
- [ ] All interactions work on touch

---

## ✅ Test 8: Keyboard Accessibility

### Steps:
1. Reload page
2. Press **Tab** repeatedly
3. Navigate to theme toggle
4. Use **Space** or **Enter** to activate
5. Open command palette with **⌘K**
6. Use **↑↓** to navigate
7. Press **Tab** to move through buttons

### Expected Results:
- [ ] All interactive elements are keyboard accessible
- [ ] Focus indicators are visible
- [ ] Tab order is logical
- [ ] Keyboard shortcuts work globally

---

## ✅ Test 9: Cross-Browser Check

Test in multiple browsers if available:

### Chrome/Edge:
- [ ] All features work
- [ ] No console errors
- [ ] Manifest loads correctly

### Firefox:
- [ ] All features work
- [ ] Theme toggle works
- [ ] Command palette works

### Safari (if on Mac):
- [ ] All features work
- [ ] iOS Safari support (if testing mobile)

---

## 🐛 Known Issues

### Issue 1: cmdk TypeScript Error
**Error**: `Cannot find module 'cmdk'`
**Status**: Benign - package is installed, TypeScript config issue
**Impact**: None - functionality works fine
**Fix**: Run `npm install` to refresh

### Issue 2: Missing PWA Icons
**Warning**: Icon files not found (icon-192.png, etc.)
**Status**: Expected - icons need to be created
**Impact**: Manifest loads but install button may not appear
**Fix**: Create icon files as documented

---

## ✅ Success Criteria

All enhancements are working if:

1. ✅ Theme toggle appears and works
2. ✅ Theme persists across reloads
3. ✅ Command palette opens with ⌘K
4. ✅ Command palette search works
5. ✅ Manifest loads in DevTools
6. ✅ Animations are smooth
7. ✅ All keyboard accessible
8. ✅ Mobile responsive

---

## 📊 Performance Check

### Lighthouse Test (Optional):
```bash
npm run test:lighthouse:smoke
```

### Expected Scores:
- Performance: 90+ (same as before)
- Accessibility: 95+ (same or better)
- Best Practices: 95+
- SEO: 90+
- PWA: 80+ (with icons: 100)

---

## 🎉 All Tests Passed?

**Congratulations!** Your UI enhancements are working correctly.

### Next Actions:
1. Create PWA icons (see `UI_ENHANCEMENTS_MIGRATION_GUIDE.md`)
2. Add E2E tests for keyboard shortcuts
3. Monitor production metrics
4. Consider adding more shortcuts to command palette

---

## 🆘 Need Help?

If tests fail:
1. Check `UI_ENHANCEMENTS_MIGRATION_GUIDE.md` troubleshooting section
2. Verify all files are in correct locations
3. Run `npm install` to ensure dependencies
4. Check browser console for errors
5. Review `UI_ENHANCEMENTS_IMPLEMENTATION.md` for details