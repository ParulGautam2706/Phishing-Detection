document.addEventListener('DOMContentLoaded', () => {
    const contactForm = document.getElementById('contactForm');
    const fullNameInput = document.getElementById('fullName');
    const emailInput = document.getElementById('email');
    const phoneInput = document.getElementById('phone');
    const subjectInput = document.getElementById('subject');
    const messageInput = document.getElementById('message');
    const charCountSpan = document.getElementById('charCount');
    const successMessage = document.getElementById('successMessage');
    const errorMessage = document.getElementById('errorMessage');

    // Character counter for message
    messageInput.addEventListener('input', () => {
        let count = messageInput.value.length;
        charCountSpan.textContent = count;
        
        if (count > 500) {
            messageInput.value = messageInput.value.substring(0, 500);
            charCountSpan.textContent = 500;
        }
    });

    // Validation functions
    const validators = {
        fullName: (value) => {
            const trimmed = value.trim();
            if (!trimmed) return { valid: false, message: 'Full name is required' };
            if (trimmed.length < 2) return { valid: false, message: 'Name must be at least 2 characters' };
            if (!/^[a-zA-Z\s'-]+$/.test(trimmed)) return { valid: false, message: 'Name contains invalid characters' };
            return { valid: true };
        },
        email: (value) => {
            const trimmed = value.trim();
            const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            if (!trimmed) return { valid: false, message: 'Email address is required' };
            if (!emailRegex.test(trimmed)) return { valid: false, message: 'Please enter a valid email address' };
            return { valid: true };
        },
        phone: (value) => {
            if (!value.trim()) return { valid: true }; // Phone is optional
            const phoneRegex = /^[\d\s\-\+\(\)]+$/;
            if (!phoneRegex.test(value)) return { valid: false, message: 'Please enter a valid phone number' };
            if (value.replace(/\D/g, '').length < 10) return { valid: false, message: 'Phone number should have at least 10 digits' };
            return { valid: true };
        },
        subject: (value) => {
            const trimmed = value.trim();
            if (!trimmed) return { valid: false, message: 'Subject is required' };
            if (trimmed.length < 3) return { valid: false, message: 'Subject must be at least 3 characters' };
            if (trimmed.length > 100) return { valid: false, message: 'Subject must not exceed 100 characters' };
            return { valid: true };
        },
        message: (value) => {
            const trimmed = value.trim();
            if (!trimmed) return { valid: false, message: 'Message is required' };
            if (trimmed.length < 10) return { valid: false, message: 'Message must be at least 10 characters' };
            if (trimmed.length > 500) return { valid: false, message: 'Message cannot exceed 500 characters' };
            return { valid: true };
        }
    };

    // Display error message
    const showError = (inputId, message) => {
        const errorElement = document.getElementById(`${inputId}Error`);
        if (errorElement) {
            errorElement.textContent = message;
            errorElement.style.display = 'block';
        }
        document.getElementById(inputId).classList.add('input-error');
    };

    // Clear error message
    const clearError = (inputId) => {
        const errorElement = document.getElementById(`${inputId}Error`);
        if (errorElement) {
            errorElement.textContent = '';
            errorElement.style.display = 'none';
        }
        document.getElementById(inputId).classList.remove('input-error');
    };

    // Real-time validation on blur
    fullNameInput.addEventListener('blur', () => {
        const validation = validators.fullName(fullNameInput.value);
        if (!validation.valid) {
            showError('fullName', validation.message);
        } else {
            clearError('fullName');
        }
    });

    emailInput.addEventListener('blur', () => {
        const validation = validators.email(emailInput.value);
        if (!validation.valid) {
            showError('email', validation.message);
        } else {
            clearError('email');
        }
    });

    phoneInput.addEventListener('blur', () => {
        const validation = validators.phone(phoneInput.value);
        if (!validation.valid) {
            showError('phone', validation.message);
        } else {
            clearError('phone');
        }
    });

    subjectInput.addEventListener('blur', () => {
        const validation = validators.subject(subjectInput.value);
        if (!validation.valid) {
            showError('subject', validation.message);
        } else {
            clearError('subject');
        }
    });

    messageInput.addEventListener('blur', () => {
        const validation = validators.message(messageInput.value);
        if (!validation.valid) {
            showError('message', validation.message);
        } else {
            clearError('message');
        }
    });

    // Clear errors when typing
    [fullNameInput, emailInput, phoneInput, subjectInput, messageInput].forEach(input => {
        input.addEventListener('input', () => {
            const inputId = input.id;
            const errorElement = document.getElementById(`${inputId}Error`);
            if (errorElement && errorElement.textContent) {
                clearError(inputId);
            }
        });
    });

    // Form submission
    contactForm.addEventListener('submit', (e) => {
        e.preventDefault();

        // Clear previous messages
        successMessage.style.display = 'none';
        errorMessage.style.display = 'none';
        successMessage.textContent = '';
        errorMessage.textContent = '';

        // Validate all fields
        let isValid = true;
        const validations = {
            fullName: validators.fullName(fullNameInput.value),
            email: validators.email(emailInput.value),
            phone: validators.phone(phoneInput.value),
            subject: validators.subject(subjectInput.value),
            message: validators.message(messageInput.value)
        };

        // Show errors for invalid fields
        Object.entries(validations).forEach(([field, validation]) => {
            if (!validation.valid) {
                showError(field, validation.message);
                isValid = false;
            } else {
                clearError(field);
            }
        });

        if (!isValid) {
            errorMessage.textContent = 'Please fix the errors above and try again.';
            errorMessage.style.display = 'block';
            return;
        }

        // Collect form data
        const formData = {
            fullName: fullNameInput.value.trim(),
            email: emailInput.value.trim(),
            phone: phoneInput.value.trim(),
            subject: subjectInput.value.trim(),
            category: document.getElementById('category').value,
            message: messageInput.value.trim(),
            subscribe: document.getElementById('subscribe').checked,
            timestamp: new Date().toLocaleString()
        };

        // Simulate form submission
        submitForm(formData);
    });

    // Form submission handler
    function submitForm(formData) {
        // Show loading state
        const submitBtn = contactForm.querySelector('button[type="submit"]');
        const originalText = submitBtn.innerHTML;
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span>Sending...</span>';

        // Simulate API call with timeout
        setTimeout(() => {
            // Success response
            successMessage.innerHTML = `
                <strong>Thank You!</strong><br>
                Thank you for contacting SecureLink, ${formData.fullName}. 
                We've received your message and will get back to you shortly at ${formData.email}.
            `;
            successMessage.style.display = 'block';

            // Log form data (in production, this would be sent to a server)
            console.log('Form Submitted:', formData);

            // Reset form
            contactForm.reset();
            charCountSpan.textContent = '0';

            // Clear success message after 5 seconds
            setTimeout(() => {
                successMessage.style.display = 'none';
            }, 5000);

            // Restore button
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalText;

            // Scroll to top of form
            contactForm.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }, 1500);
    }

    // FAQ Toggle
    const faqQuestions = document.querySelectorAll('.faq-question');
    faqQuestions.forEach(question => {
        question.addEventListener('click', () => {
            const faqItem = question.parentElement;
            const isExpanded = question.getAttribute('aria-expanded') === 'true';
            
            // Close all other FAQs
            document.querySelectorAll('.faq-item').forEach(item => {
                if (item !== faqItem) {
                    item.querySelector('.faq-question').setAttribute('aria-expanded', 'false');
                    item.classList.remove('active');
                }
            });

            // Toggle current FAQ
            question.setAttribute('aria-expanded', !isExpanded);
            faqItem.classList.toggle('active');
        });
    });

    // Live Chat Button (placeholder)
    const chatBtn = document.querySelector('.btn-chat');
    if (chatBtn) {
        chatBtn.addEventListener('click', () => {
            alert('Live chat feature coming soon! Please use the contact form or call our support team.');
        });
    }

    // Mobile navigation toggle
    const navToggle = document.querySelector('.nav-toggle');
    const mainNav = document.querySelector('.main-nav');
    navToggle && navToggle.addEventListener('click', () => {
        mainNav.classList.toggle('open');
    });
});
