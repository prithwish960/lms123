from django.shortcuts import redirect, render
from app.models import Categories, Course, Level, Video, UserCource, Payment
from django.template.loader import render_to_string
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Sum
from django.views.decorators.csrf import csrf_exempt

from .settings import *
import razorpay
from time import time

client = razorpay.Client(auth=(KEY_ID,KEY_SECRET))


def BASE(request):
    return render(request, 'base.html')

def HOME(request):
    category = Categories.objects.all().order_by('id')[0:5]
    course = Course.objects.filter(status= 'PUBLISH')
    context = {
        'category': category,
        'course': course,
    }
    return render(request, 'Main/home.html', context)

def SINGLE_COURSE(request):
    category = Categories.get_all_category(Categories)
    level = Level.objects.all()
    course = Course.objects.all()
    FreeCourse_count = Course.objects.filter(price=0).count()
    PaidCourse_count = Course.objects.filter(price__gte=1).count()
    context = {
        'category': category,
        'level': level,
        'course': course,
        'FreeCourse_count': FreeCourse_count,
        'PaidCourse_count': PaidCourse_count,
    }
    return render(request, 'Main/single_course.html', context)

def filter_data(request):
    categories = request.GET.getlist('category[]')
    level = request.GET.getlist('level[]')
    price = request.GET.getlist('price[]')
    #print(price)


    if price == ['pricefree']:
       course = Course.objects.filter(price=0)
    elif price == ['pricepaid']:
       course = Course.objects.filter(price__gte=1)
    elif price == ['priceall']:
       course = Course.objects.all()
    elif categories:
       course = Course.objects.filter(category__id__in=categories).order_by('-id')
    elif level:
       course = Course.objects.filter(level__id__in = level).order_by('-id')
    else:
       course = Course.objects.all().order_by('-id')


    t = render_to_string('ajax/course.html', {'course': course})

    return JsonResponse({'data': t})

def CONTACT_US(request):
    category = Categories.get_all_category(Categories)

    context = {
        'category': category,
    }
    return render(request, 'Main/contact_us.html', context)

def ABOUT_US(request):
    category = Categories.get_all_category(Categories)

    context = {
        'category': category,
    }
    return render(request, 'Main/about_us.html', context)


def SEARCH_COURSE(request):
    category = Categories.get_all_category(Categories)
    query = request.GET['query']
    course = Course.objects.filter(title__icontains = query)
    context = {
        'course':course,
        'category': category,
    }
    return render(request,'search/search.html',context)

def SEARCH_COURSE_ENROLL(request):
    #enrolled = UserCource.get_all_category(UserCource)
    searched_query = request.GET['search_query']
    course = UserCource.objects.filter(title__icontains = searched_query)
    context = {
        'course': course,
    }
    return render(request, 'search/search_course_enroll.html', context)


def COURSE_DETAILS(request, slug):
    category = Categories.get_all_category(Categories)
    time_duration = Video.objects.filter(course__slug = slug).aggregate(sum=Sum('time_duration'))

    course_id = Course.objects.get(slug=slug)
    try:
        check_enroll = UserCource.objects.get(user=request.user, course=course_id)
    except UserCource.DoesNotExist:
        check_enroll = None

    course = Course.objects.filter(slug=slug)
    if course.exists():
        course = course.first()
    else:
        return redirect('404')

    context = {
        'course':course,
        'category': category,
        'time_duration': time_duration,
        'check_enroll': check_enroll,
    }
    return render(request, 'course/course_details.html', context)

def PAGE_NOT_FOUND(request):
    category = Categories.get_all_category(Categories)

    context = {
        'category': category,
    }
    return render(request, 'error/404.html', context)

def CHECKOUT(request, slug):
    course = Course.objects.get(slug = slug)
    action = request.GET.get('action')
    order = None
    if course.price == 0:
        course = UserCource(
            user = request.user,
            course = course,
        )
        course.save()
        messages.success(request, 'Course successfully Enrolled')


        return redirect('my_course')
    elif action == 'create_payment':
        if request.method == "POST":
            first_name = request.POST.get('billing_first_name')
            last_name = request.POST.get('billing_last_name')
            country = request.POST.get('billing_country')
            address_1 = request.POST.get('billing_address_1')
            address_2 = request.POST.get('billing_address_2')
            city = request.POST.get('billing_city')
            state = request.POST.get('billing_state')
            postcode = request.POST.get('billing_postcode')
            phone = request.POST.get('billing_phone')
            email = request.POST.get('billing_email')
            order_comments = request.POST.get('order_comments')

            net_discount = (course.discount/100)
            net_amount = (course.price * 100)
            amount = ((course.price * 100) - (net_discount * net_amount))
            currency = "INR"
            notes = {
                "name": f'{first_name}  {last_name} ',
                "country": country,
                "city": city,
                "state": state,
                "postcode": postcode,
                "phone": phone,
                "email": email,
                "order_comments": order_comments,
            }
            receipt = f"SKola-{int(time())}"
            order = client.order.create(
                {
                    'receipt': receipt,
                    'notes': notes,
                    'amount': amount,
                    'currency': currency,
                }
            )
            payment = Payment(
                course=course,
                user=request.user,
                order_id=order.get('id')
            )
            payment.save()

    context = {
        'course': course,
        'order': order,
    }

    return render(request, 'checkout/checkout.html', context)

def MY_COURSE(request):
    course = UserCource.objects.filter(user = request.user)

    context = {
        'course': course,
    }
    return render(request, 'course/my-course.html', context)

@csrf_exempt
def VERIFY_PAYMENT(request):
    if request.method == "POST":
        data = request.POST
        try:
            client.utility.verify_payment_signature(data)
            razorpay_order_id = data['razorpay_order_id']
            razorpay_payment_id = data['razorpay_order_id']

            payment = Payment.objects.get(order_id=razorpay_order_id)
            payment.payment_id = razorpay_payment_id
            payment.status = True

            usercourse = UserCource(
                user = payment.user,
                course = payment.course,
            )
            usercourse.save()
            payment.user_course = usercourse
            payment.save()

            context = {
                'data': data,
                'payment': payment,
            }

            return render(request, 'verify_payment/success.html', context)
        except:
            return render(request, 'verify_payment/fail.html')

