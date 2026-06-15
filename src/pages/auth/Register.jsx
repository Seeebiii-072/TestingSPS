import { Link, useNavigate } from 'react-router-dom';
import { useState } from 'react';
import Brand from '../../components/common/Brand';
import authService from '../../services/authService.js';

const roles = [
  ['intern', 'Intern'],
  ['employee', 'Employee'],
  ['agent', 'Agent'],
  ['security_admin', 'Security Admin'],
  ['manager', 'Manager'],
  ['administrator', 'Administrator'],
];

export default function Register() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    email: '',
    fullName: '',
    password: '',
    role: 'intern',
  });
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const updateField = (event) => {
    const { name, value } = event.target;
    setForm((current) => ({ ...current, [name]: value }));
  };

  const submitRegister = async (event) => {
    event.preventDefault();
    setError('');
    setIsSubmitting(true);
    try {
      await authService.register(form.email, form.fullName, form.password, form.role);
      navigate('/login', { replace: true });
    } catch {
      setError('Registration failed. The email may already be registered.');
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
          <h1>Create your SecureDesk account</h1>
          <p>Register a requester, agent, security, manager, or admin account.</p>
        </div>
        <form className="login-form" onSubmit={submitRegister}>
          <label>
            Full name
            <input name="fullName" required value={form.fullName} onChange={updateField} />
          </label>
          <label>
            Work email
            <input name="email" type="email" required value={form.email} onChange={updateField} />
          </label>
          <label>
            Password
            <input name="password" type="password" minLength="8" required value={form.password} onChange={updateField} />
          </label>
          <label>
            Role
            <select name="role" value={form.role} onChange={updateField}>
              {roles.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          {error && <p className="form-error" role="alert">{error}</p>}
          <button className="primary-button" type="submit" disabled={isSubmitting}>
            {isSubmitting ? 'Creating account...' : 'Create account'}
          </button>
        </form>
        <p className="login-panel__note">
          Already have an account? <Link to="/login">Sign in</Link>.
        </p>
      </section>
      <aside className="login-visual">
        <div className="login-visual__content">
          <span className="login-visual__label">SPS SecureDesk AI</span>
          <h2>Role-based access for every helpdesk workflow.</h2>
          <p>Each account redirects to the workspace that matches its backend role.</p>
        </div>
      </aside>
    </main>
  );
}
