import { supabase } from './supabaseClient.js';

// Check if user is logged in
async function checkUser() {
  try {
    const { data: { user } } = await supabase.auth.getUser();
    
    if (user) {
      document.querySelectorAll('.logged-out').forEach(el => el.classList.add('d-none'));
      document.querySelectorAll('.logged-in').forEach(el => el.classList.remove('d-none'));
      
      const userEmail = document.getElementById('userEmail');
      if (userEmail) {
        userEmail.textContent = user.email;
      }
    } else {
      document.querySelectorAll('.logged-out').forEach(el => el.classList.remove('d-none'));
      document.querySelectorAll('.logged-in').forEach(el => el.classList.add('d-none'));
    }
  } catch (error) {
    console.error('Error checking user:', error.message);
  }
}

// Sign Up
async function handleSignup(event) {
  event.preventDefault();
  const form = event.target;
  const email = form.querySelector('#signupEmail').value;
  const password = form.querySelector('#signupPassword').value;
  
  // Disable the button and show loading state
  const button = form.querySelector('button[type="submit"]');
  const originalText = button.textContent;
  button.disabled = true;
  button.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Signing up...';
  
  try {
    const { data, error } = await supabase.auth.signUp({ email, password });
    
    if (error) {
      throw new Error(error.message);
    }
    
    // Show success message
    const alert = document.createElement('div');
    alert.className = 'alert alert-success';
    alert.innerHTML = 'Signup successful! Check your email for confirmation.';
    form.prepend(alert);
    
    // Reset form
    form.reset();
    
    // Close modal after 3 seconds
    setTimeout(() => {
      bootstrap.Modal.getInstance(document.getElementById('signupModal')).hide();
      alert.remove();
    }, 3000);
    
    await checkUser();
  } catch (error) {
    // Show error message
    const alert = document.createElement('div');
    alert.className = 'alert alert-danger';
    alert.innerHTML = error.message;
    form.prepend(alert);
    
    // Remove error message after 3 seconds
    setTimeout(() => {
      alert.remove();
    }, 3000);
  } finally {
    // Re-enable the button
    button.disabled = false;
    button.textContent = originalText;
  }
}

// Login
async function handleLogin(event) {
  event.preventDefault();
  const form = event.target;
  const email = form.querySelector('#loginEmail').value;
  const password = form.querySelector('#loginPassword').value;
  
  // Disable the button and show loading state
  const button = form.querySelector('button[type="submit"]');
  const originalText = button.textContent;
  button.disabled = true;
  button.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Logging in...';
  
  try {
    const { data, error } = await supabase.auth.signInWithPassword({ email, password });
    
    if (error) {
      throw new Error(error.message);
    }
    
    // Show success message
    const alert = document.createElement('div');
    alert.className = 'alert alert-success';
    alert.innerHTML = 'Logged in successfully!';
    form.prepend(alert);
    
    // Reset form
    form.reset();
    
    // Close modal after 3 seconds
    setTimeout(() => {
      bootstrap.Modal.getInstance(document.getElementById('loginModal')).hide();
      alert.remove();
    }, 3000);
    
    await checkUser();
  } catch (error) {
    // Show error message
    const alert = document.createElement('div');
    alert.className = 'alert alert-danger';
    alert.innerHTML = error.message;
    form.prepend(alert);
    
    // Remove error message after 3 seconds
    setTimeout(() => {
      alert.remove();
    }, 3000);
  } finally {
    // Re-enable the button
    button.disabled = false;
    button.textContent = originalText;
  }
}

// Logout
async function handleLogout() {
  const { error } = await supabase.auth.signOut();
  
  if (error) {
    console.error('Error logging out:', error.message);
  }
  
  // Fully reset UI
  await checkUser();
  window.location.reload();  // Optional: force clear state
}

// Show/hide modals
function showLogin() {
  const loginModal = new bootstrap.Modal(document.getElementById('loginModal'));
  loginModal.show();
}

function showSignup() {
  const signupModal = new bootstrap.Modal(document.getElementById('signupModal'));
  signupModal.show();
}

// Initialize - check user status when the page loads
document.addEventListener('DOMContentLoaded', checkUser);

// Export functions for global access
window.handleSignup = handleSignup;
window.handleLogin = handleLogin;
window.handleLogout = handleLogout;
window.showLogin = showLogin;
window.showSignup = showSignup; 