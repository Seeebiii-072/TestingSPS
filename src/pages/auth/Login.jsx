import { Link, useNavigate } from 'react-router-dom';
import { useEffect, useState } from 'react';
import Brand from '../../components/common/Brand';
import GuestReportForm from '../../components/auth/GuestReportForm';
import authService from '../../services/authService.js';
import { ROLES } from '../../config/constants.js';
import { useAuth } from '../../context/AuthContext';

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
  const { login, user } = useAuth();

  useEffect(() => {
    const currentUser = user || authService.getCurrentUser();
    if (currentUser?.role && roleRedirects[currentUser.role]) {
      navigate(roleRedirects[currentUser.role], { replace: true });
    }
  }, [navigate, user]);

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isGuestOpen, setIsGuestOpen] = useState(false);

  const submitLogin = async (event) => {
    event.preventDefault();
    setError('');
    setIsSubmitting(true);
    try {
      const loggedInUser = await login(email, password);
      navigate(roleRedirects[loggedInUser.role] || '/requester', { replace: true });
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
          <h1>{isGuestOpen ? 'Submit a Request' : 'Sign in to SecureDesk AI'}</h1>
          <p>
            {isGuestOpen
              ? 'Submit a service request without creating an account.'
              : 'Access the enterprise helpdesk workspace for IT, security, cloud, and operational support.'}
          </p>
        </div>

        {!isGuestOpen ? (
          <>
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
              <Link to="/forgot-password">Forgot Password?</Link>
            </p>
          </>
        ) : (
          <GuestReportForm />
        )}

        <div className="login-panel__guest-toggle-wrapper">
          <button
            className="login-panel__guest-toggle"
            type="button"
            onClick={() => setIsGuestOpen((v) => !v)}
            aria-expanded={isGuestOpen}
          >
            <span aria-hidden="true">{isGuestOpen ? '←' : '📩'}</span>
            {isGuestOpen ? 'Back to Sign In' : 'New to SPS? Submit a Request'}
            <span className={`login-panel__guest-chevron ${isGuestOpen ? 'login-panel__guest-chevron--open' : ''}`} aria-hidden="true" style={{ display: isGuestOpen ? 'none' : 'inline' }}>▾</span>
          </button>
        </div>
      </section>
      <aside className="login-visual">
        {/* Decorative gradient orbs */}
        <div className="login-visual__orb login-visual__orb--1" aria-hidden="true" />
        <div className="login-visual__orb login-visual__orb--2" aria-hidden="true" />
        <div className="login-visual__orb login-visual__orb--3" aria-hidden="true" />

        {/* Featured hero text */}
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