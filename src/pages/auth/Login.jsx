import { Link, useNavigate } from 'react-router-dom';
import { useState } from 'react';
import Brand from '../../components/common/Brand';
import authService from '../../services/authService.js';
import { ROLES } from '../../config/constants.js';

const roleRedirects = {
  [ROLES.INTERN]: '/requester',
  [ROLES.EMPLOYEE]: '/requester',
  [ROLES.AGENT]: '/agent',
  [ROLES.SECURITY_ADMIN]: '/security',
  [ROLES.MANAGER]: '/manager',
  [ROLES.ADMINISTRATOR]: '/admin',
};

export default function Login() {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const submitLogin = async (event) => {
    event.preventDefault();
    setError('');
    setIsSubmitting(true);
    try {
      const user = await authService.login(email, password);
      navigate(roleRedirects[user.role] || '/requester', { replace: true });
    } catch {
      setError('Login failed. Please check your email and password.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="login-page">
      <section className="login-panel">
        <Brand />
        <div className="login-panel__intro">
          <p className="eyebrow">Secure service operations</p>
          <h1>Sign in to SecureDesk AI</h1>
          <p>
            Access the enterprise helpdesk workspace for IT, security, cloud,
            and operational support.
          </p>
        </div>
        <form className="login-form" onSubmit={submitLogin}>
          <label>
            Work email
            <input
              type="email"
              placeholder="name@company.com"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </label>
          <label>
            Password
            <input
              type="password"
              placeholder="********"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </label>
          {error && <p className="form-error" role="alert">{error}</p>}
          <button className="primary-button" type="submit" disabled={isSubmitting}>
            {isSubmitting ? 'Signing in...' : 'Sign in'}
          </button>
        </form>
        <p className="login-panel__note">
          New to SecureDesk? <Link to="/register">Create an account</Link>.
        </p>
      </section>
      <aside className="login-visual">
        <div className="login-visual__content">
          <span className="login-visual__label">SPS SecureDesk AI</span>
          <h2>One secure workspace for enterprise support operations.</h2>
          <p>
            A focused foundation for requester service, agent workflows,
            cybersecurity approvals, management reporting, and administration.
          </p>
        </div>
      </aside>
    </main>
  );
}
