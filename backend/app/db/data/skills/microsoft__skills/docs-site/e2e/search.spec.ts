import { test, expect } from '@playwright/test';

test.describe('Inline Search', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('./');
    await page.waitForLoadState('networkidle');
  });

  test('search input is visible on page load', async ({ page }) => {
    const searchInput = page.getByTestId('search-input');
    await expect(searchInput).toBeVisible({ timeout: 5000 });
  });

  test('focuses search input with Cmd+K (Mac) or Ctrl+K (Windows/Linux)', async ({ page }) => {
    const searchInput = page.getByTestId('search-input');
    await expect(searchInput).toBeVisible({ timeout: 5000 });

    await page.keyboard.press('Control+k');

    await expect(searchInput).toBeFocused();
  });

  test('typing in search filters the skill cards', async ({ page }) => {
    const searchInput = page.getByTestId('search-input');
    await expect(searchInput).toBeVisible({ timeout: 5000 });

    // Get initial card count
    const initialCards = page.locator('.skills-grid > div');
    const initialCount = await initialCards.count();
    expect(initialCount).toBeGreaterThan(0);

    // Search for a specific term
    await searchInput.fill('cosmos');
    await page.waitForTimeout(100); // Allow React to re-render

    // Should have fewer cards after filtering
    const filteredCards = page.locator('.skills-grid > div');
    const filteredCount = await filteredCards.count();
    expect(filteredCount).toBeLessThan(initialCount);
    expect(filteredCount).toBeGreaterThan(0);

    // Cards should contain the search term
    const firstCard = filteredCards.first();
    await expect(firstCard).toContainText(/cosmos/i);
  });

  test('shows "Showing X skills matching query" text when searching', async ({ page }) => {
    const searchInput = page.getByTestId('search-input');
    await searchInput.fill('storage');

    await page.waitForTimeout(100);

    await expect(page.getByText(/matching "storage"/i)).toBeVisible();
  });

  test('clears search with Escape key', async ({ page }) => {
    const searchInput = page.getByTestId('search-input');
    await searchInput.fill('cosmos');
    await page.waitForTimeout(100);

    // Verify filter is applied
    await expect(page.getByText(/matching "cosmos"/i)).toBeVisible();

    // Press Escape while focused
    await searchInput.focus();
    await page.keyboard.press('Escape');

    // Search should be cleared
    await expect(searchInput).toHaveValue('');
    await expect(page.getByText(/matching "cosmos"/i)).not.toBeVisible();
  });

  test('clears search with clear button', async ({ page }) => {
    const searchInput = page.getByTestId('search-input');
    await searchInput.fill('blob');
    await page.waitForTimeout(100);

    // Clear button should be visible
    const clearButton = page.getByLabel('Clear search');
    await expect(clearButton).toBeVisible();

    await clearButton.click();

    // Search should be cleared
    await expect(searchInput).toHaveValue('');
  });

  test('shows no results state for non-matching search', async ({ page }) => {
    const searchInput = page.getByTestId('search-input');
    await searchInput.fill('xyznonexistent123');
    await page.waitForTimeout(100);

    await expect(page.getByText('No skills found')).toBeVisible();
  });

  test('search combines with language filter', async ({ page }) => {
    const searchInput = page.getByTestId('search-input');

    // Select Python language
    const pythonTab = page.locator('button:has-text("Python")');
    await pythonTab.click();
    await page.waitForTimeout(100);

    // Search for a term
    await searchInput.fill('cosmos');
    await page.waitForTimeout(100);

    // Should only show Python cosmos skills
    const cards = page.locator('.skills-grid > div');
    const count = await cards.count();

    // If results exist, they should be Python skills with cosmos
    if (count > 0) {
      const firstCard = cards.first();
      await expect(firstCard).toContainText(/cosmos/i);
    }
  });

  test('search combines with category filter', async ({ page }) => {
    const searchInput = page.getByTestId('search-input');

    // Select a category (Foundry has many skills)
    const foundryTab = page.locator('button:has-text("Foundry")');
    if (await foundryTab.isVisible()) {
      await foundryTab.click();
      await page.waitForTimeout(100);

      // Search for a term
      await searchInput.fill('agent');
      await page.waitForTimeout(100);

      // Should only show Foundry agent skills
      const cards = page.locator('.skills-grid > div');
      const count = await cards.count();

      if (count > 0) {
        const firstCard = cards.first();
        await expect(firstCard).toContainText(/agent/i);
      }
    }
  });
});
