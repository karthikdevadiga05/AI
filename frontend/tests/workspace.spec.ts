import { test, expect } from '@playwright/test';
import path from 'node:path';

test('register, upload, ask, inspect citation, restore history, and delete', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', e => errors.push(e.message));
  await page.goto('/');
  await page.getByRole('button', { name: 'Create an account' }).click();
  await page.getByLabel('Username', { exact: true }).fill('e2e-' + Date.now());
  await page.getByLabel('Password', { exact: true }).fill('e2e-password-123');
  await page.getByRole('button', { name: 'Create workspace' }).click();
  await expect(page.getByRole('heading', { name: 'Ask. Discover. Understand.' })).toBeVisible();
  await page.locator('input[type=file]').setInputFiles(path.resolve('../samples/distributed-systems-notes.pdf'));
  await expect(page.getByRole('status')).toContainText('1 document added');
  await page.getByRole('textbox', { name: 'Ask a question' }).fill('What is the HDFS replication factor?');
  await page.getByRole('button', { name: 'Send question' }).click();
  await expect(page.locator('.answer-paragraph').first()).toContainText('replication factor is three');
  await page.getByRole('button', { name: 'View source 1', exact: true }).click();
  await expect(page.getByRole('dialog', { name: 'Source preview' })).toBeVisible();
  await expect(page.locator('.modal-header')).toContainText('PDF page 2');
  await page.keyboard.press('Escape');
  await page.getByRole('button', { name: 'New conversation' }).click();
  await page.getByRole('button', { name: 'What is the HDFS replication factor?', exact: true }).click();
  await expect(page.locator('.answer-paragraph').first()).toContainText('replication factor is three');
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Export conversation' }).click();
  expect((await download).suggestedFilename()).toBe('citewise-conversation.md');
  await page.getByRole('textbox', { name: 'Ask a question' }).fill('Who won Wimbledon?');
  await page.getByRole('button', { name: 'Send question' }).click();
  await expect(page.getByText('Not enough supporting evidence was found in the selected documents.')).toBeVisible();
  page.on('dialog', d => d.accept());
  await page.getByRole('button', { name: 'Delete distributed-systems-notes.pdf', exact: true }).click();
  await expect(page.getByText('A fresh page.')).toBeVisible();
  expect(errors).toEqual([]);
});

test('mobile layout has no horizontal overflow', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  await page.getByRole('button', { name: 'Create an account' }).click();
  await page.getByLabel('Username', { exact: true }).fill('mobile-' + Date.now());
  await page.getByLabel('Password', { exact: true }).fill('e2e-password-123');
  await page.getByRole('button', { name: 'Create workspace' }).click();
  await expect(page.getByRole('heading', { name: 'Ask. Discover. Understand.' })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await expect(page.getByRole('button', { name: 'Add documents' })).toBeVisible();
});
