import { render } from '@testing-library/react'
import { expectNoA11yViolations } from '../../test/axe-helper'

describe('Page-level accessibility', () => {
  it('renders a basic page layout without a11y violations', async () => {
    const { container } = render(
      <main aria-label="Test page">
        <h1>Test Page</h1>
        <nav aria-label="Primary">
          <ul>
            <li><a href="/dashboard">Dashboard</a></li>
            <li><a href="/incidents">Incidents</a></li>
          </ul>
        </nav>
        <section aria-label="Content">
          <p>Page content goes here</p>
        </section>
      </main>
    )
    await expectNoA11yViolations(container)
  })

  it('form layout has proper labels and structure', async () => {
    const { container } = render(
      <main aria-label="Form page">
        <h1>Create Incident</h1>
        <form aria-label="Incident form">
          <div>
            <label htmlFor="title">Title</label>
            <input id="title" type="text" name="title" required />
          </div>
          <div>
            <label htmlFor="description">Description</label>
            <textarea id="description" name="description" />
          </div>
          <div>
            <label htmlFor="severity">Severity</label>
            <select id="severity" name="severity">
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
            </select>
          </div>
          <button type="submit">Submit</button>
        </form>
      </main>
    )
    await expectNoA11yViolations(container)
  })

  it('data table layout is accessible', async () => {
    const { container } = render(
      <main aria-label="List page">
        <h1>Risk Register</h1>
        <table>
          <caption>Active risks</caption>
          <thead>
            <tr>
              <th scope="col">Reference</th>
              <th scope="col">Title</th>
              <th scope="col">Level</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>RISK-001</td>
              <td>Data breach risk</td>
              <td>High</td>
            </tr>
          </tbody>
        </table>
      </main>
    )
    await expectNoA11yViolations(container)
  })
})
